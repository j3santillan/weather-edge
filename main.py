"""Weather Edge — 4-model ensemble voting engine.

Pipeline:
  1. Fetch markets: Polymarket + Kalshi
  2. Merge cross-platform (fuzzy-match same events)
  3. Parse market questions with Claude → city, metric, threshold, date
  4. Fetch 4-model ensemble (ECMWF/GFS/NAM/UKMET) per city
  5. Apply bias corrections → vote count → true probability
  6. Compare vs Polymarket + Kalshi prices → pick best edge
  7. Filter: only signals where |edge| >= 15%
  8. Run 90-day historical backtest
  9. Log + generate dashboard
"""
import logging
import os
import sys
from datetime import datetime, timezone
from difflib import SequenceMatcher


def _load_dotenv() -> None:
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip().strip("\"'"))


_load_dotenv()

os.makedirs("logs",   exist_ok=True)
os.makedirs("output", exist_ok=True)
os.makedirs("data",   exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/weather_edge.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

from open_meteo_client import geocode
from ensemble_client import get_ensemble
from bias_tracker import get_corrections
from probability_engine import compute_probability
from polymarket_client import get_weather_markets as poly_markets
from kalshi_client import get_weather_markets as kalshi_markets
from market_parser import parse_markets
from backtester import run_backtest
from dashboard import generate_dashboard, DASHBOARD_PATH
from signal_logger import log_signals, get_history

EDGE_THRESHOLD = 15.0   # minimum |edge %| to emit a signal
MATCH_RATIO    = 0.72   # minimum similarity for cross-platform dedup


def run() -> None:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    logger.info(f"=== Weather Edge run {run_id} ===")

    # ── 1. Fetch markets ────────────────────────────────────────────────────
    logger.info("Step 1/6: Fetching markets (Polymarket + Kalshi)...")
    poly   = poly_markets()
    kalshi = kalshi_markets()
    logger.info(f"  {len(poly)} Polymarket  |  {len(kalshi)} Kalshi")

    if not poly and not kalshi:
        logger.warning("No markets on either platform — aborting run")
        return

    merged = _merge_markets(poly, kalshi)
    logger.info(f"  → {len(merged)} merged market records")

    # ── 2. Parse with Claude ─────────────────────────────────────────────────
    logger.info("Step 2/6: Parsing market questions with Claude...")
    parsed = parse_markets(merged)
    parseable = [m for m in parsed if m.get("city") and m.get("metric") and m.get("target_date")]
    logger.info(f"  {len(parseable)}/{len(parsed)} parseable (city + metric + date)")

    # ── 3. Fetch ensemble data ────────────────────────────────────────────────
    logger.info("Step 3/6: Fetching 4-model ensemble (ECMWF/GFS/NAM/UKMET)...")
    cities_needed = {m["city"] for m in parseable}
    ensemble_data: dict[str, dict] = {}

    for city in sorted(cities_needed):
        coord = geocode(city)
        if not coord:
            logger.warning(f"  Could not geocode '{city}' — skipping")
            continue
        logger.info(f"  Fetching ensemble for {city}...")
        data = get_ensemble(city, coord["lat"], coord["lon"])
        if data:
            ensemble_data[city] = data

    logger.info(f"  Ensemble ready for {len(ensemble_data)}/{len(cities_needed)} cities")

    # ── 4. Vote count → probabilities ─────────────────────────────────────────
    logger.info("Step 4/6: Computing ensemble probabilities...")
    signals: list[dict] = []

    for mkt in parseable:
        city = mkt["city"]
        if city not in ensemble_data:
            continue

        bias   = get_corrections(city)
        result = compute_probability(
            ensemble_data[city],
            mkt.get("metric",          "temperature_2m"),
            float(mkt.get("threshold_value", 0.0)),
            mkt.get("comparison",      "above"),
            mkt.get("target_date",     ""),
            bias,
        )

        if result["total_votes"] == 0:
            logger.debug(f"  No votes for {city} / {mkt.get('question','')[:60]}")
            continue

        our_prob   = result["probability"]
        poly_price = mkt.get("polymarket_yes_price")
        kal_price  = mkt.get("kalshi_yes_price")

        # Compute edge on each available platform
        candidates: list[tuple[str, float, float]] = []
        if poly_price is not None:
            candidates.append(("polymarket", poly_price,
                                round((our_prob - poly_price) * 100, 1)))
        if kal_price is not None:
            candidates.append(("kalshi", kal_price,
                                round((our_prob - kal_price) * 100, 1)))

        if not candidates:
            continue

        # Best platform = largest absolute edge
        best_platform, market_price, edge_pct = max(candidates, key=lambda x: abs(x[2]))

        if abs(edge_pct) < EDGE_THRESHOLD:
            continue   # not enough edge

        signals.append({
            # identity
            "market_id":       mkt.get("id", ""),
            "question":        mkt.get("question", ""),
            "city":            city,
            "target_date":     mkt.get("target_date", ""),
            "metric":          mkt.get("metric"),
            "threshold":       mkt.get("threshold_value"),
            "comparison":      mkt.get("comparison"),
            # ensemble results
            "ensemble_probability": our_prob,
            "yes_votes":       result["yes_votes"],
            "total_votes":     result["total_votes"],
            "by_model":        result["by_model"],
            # prices
            "polymarket_price":  poly_price,
            "kalshi_price":      kal_price,
            "best_platform":     best_platform,
            "market_yes_price":  market_price,
            "forecast_yes_probability": our_prob,   # kept for signal_logger compat
            "edge_pct":          edge_pct,
            "signal":            "BET" if edge_pct > 0 else "FADE",
            # links
            "polymarket_url": mkt.get("polymarket_url", ""),
            "kalshi_url":     mkt.get("kalshi_url",     ""),
        })

    bet_n  = sum(1 for s in signals if s["signal"] == "BET")
    fade_n = sum(1 for s in signals if s["signal"] == "FADE")
    logger.info(f"  {len(signals)} signals ≥{EDGE_THRESHOLD}% edge  ({bet_n} BET, {fade_n} FADE)")

    # ── 5. Backtest ────────────────────────────────────────────────────────────
    logger.info("Step 5/6: Running 90-day backtest...")
    backtest = run_backtest()
    logger.info(
        f"  Backtest: {backtest['win_rate']*100:.1f}% win rate | "
        f"{backtest['total_pnl']:+.2f} P&L | "
        f"Brier {backtest['brier_score']:.4f} | "
        f"{backtest['bets_placed']} simulated bets"
    )

    # ── 6. Log + dashboard ─────────────────────────────────────────────────────
    logger.info("Step 6/6: Logging signals and generating dashboard...")
    log_signals(signals, run_id=run_id)
    history = get_history()
    generate_dashboard(signals, history, backtest)

    logger.info(f"=== Done: {bet_n} BET | {fade_n} FADE | {DASHBOARD_PATH} ===")


# ── Helpers ────────────────────────────────────────────────────────────────────

_COMMON_CAPS = {
    "will", "the", "may", "june", "july", "august", "january", "february",
    "march", "april", "september", "october", "november", "december",
    "yes", "can", "are", "for", "not", "its", "new",
}

def _city_tokens(question: str) -> set[str]:
    """Extract capitalised words (≥3 chars) minus months/common words — city candidates only."""
    import re
    return {
        w.lower() for w in re.findall(r'\b[A-Z][a-z]{2,}\b', question)
        if w.lower() not in _COMMON_CAPS
    }


def _merge_markets(poly: list, kalshi: list) -> list:
    """
    Combine Polymarket + Kalshi markets, fuzzy-matching shared events.
    Shared events → single record with both poly/kalshi prices.
    Unmatched → record with only one platform's price (other = None).

    City-alignment guard: reject a fuzzy match if the two questions share
    no capitalised tokens — prevents e.g. a Milan Polymarket market from
    being paired with an LA Kalshi market just because the sentence skeleton
    looks similar.
    """
    matched_kal_ids: set[str] = set()
    merged: list[dict] = []

    for pm in poly:
        entry = {
            **pm,
            "polymarket_yes_price": pm.get("yes_price"),
            "polymarket_url":       pm.get("url", ""),
            "kalshi_yes_price":     None,
            "kalshi_url":           "",
        }

        pq      = pm.get("question", "")
        pq_low  = pq.lower()
        p_cities = _city_tokens(pq)
        best_km = None
        best_ratio = 0.0

        for km in kalshi:
            if km["id"] in matched_kal_ids:
                continue
            kq = km.get("question", "")
            # City-alignment guard: the two questions must share at least one
            # capitalised token (city/month/etc.) — rejects cross-city false matches
            if not (p_cities & _city_tokens(kq)):
                continue
            ratio = SequenceMatcher(None, pq_low, kq.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_km = km

        if best_km and best_ratio >= MATCH_RATIO:
            matched_kal_ids.add(best_km["id"])
            entry["kalshi_yes_price"] = best_km.get("yes_price")
            entry["kalshi_url"]       = best_km.get("url", "")

        merged.append(entry)

    for km in kalshi:
        if km["id"] not in matched_kal_ids:
            merged.append({
                **km,
                "polymarket_yes_price": None,
                "polymarket_url":       "",
                "kalshi_yes_price":     km.get("yes_price"),
                "kalshi_url":           km.get("url", ""),
            })

    return merged


if __name__ == "__main__":
    run()
