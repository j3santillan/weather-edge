"""90-day historical backtest using Open-Meteo archive data.

Method:
  - Pull 90 days of actual daily weather for 10 US cities
  - For each rolling 14-day window, compute a base-rate forecast
    (% of past 14 days that crossed a threshold)
  - Compare forecast vs actual outcome
  - Simulate bets where |signal| > 15%
  - Report win rate, P&L, Brier score

This is a calibration proxy — it measures how well rolling base rates
predict threshold crossings, establishing a baseline the ensemble model
should outperform.
"""
import logging
import time
from datetime import date, timedelta
from typing import Optional

import requests

logger = logging.getLogger(__name__)

ARCHIVE_API = "https://archive-api.open-meteo.com/v1/archive"

BACKTEST_CITIES = {
    "New York":    (40.71, -74.01),
    "Los Angeles": (34.05, -118.24),
    "Chicago":     (41.88, -87.63),
    "Miami":       (25.76, -80.19),
    "Seattle":     (47.61, -122.33),
    "Houston":     (29.76, -95.37),
    "Dallas":      (32.78, -96.80),
    "Atlanta":     (33.75, -84.39),
    "Boston":      (42.36, -71.06),
    "Denver":      (39.74, -104.99),
}

# (archive_variable, threshold, comparison, label)
THRESHOLDS = [
    ("temperature_2m_max",  32.0, "above", "Hot day (>32°C)"),
    ("temperature_2m_min",   0.0, "below", "Freeze (<0°C)"),
    ("precipitation_sum",    5.0, "above", "Rain day (>5mm)"),
    ("precipitation_sum",   25.0, "above", "Heavy rain (>25mm)"),
]

EDGE_MIN = 0.15   # same as live filter


def run_backtest(days: int = 90) -> dict:
    """Run full backtest. Returns performance summary dict."""
    end   = date.today()
    start = end - timedelta(days=days)
    logger.info(f"Backtest {start} → {end} ({len(BACKTEST_CITIES)} cities, {len(THRESHOLDS)} thresholds)")

    all_events: list[dict] = []

    for city, (lat, lon) in BACKTEST_CITIES.items():
        actuals = _fetch_actuals(lat, lon, str(start), str(end))
        if not actuals:
            continue

        for var, threshold, comparison, label in THRESHOLDS:
            events = _simulate(actuals, var, threshold, comparison, city, label)
            all_events.extend(events)

        time.sleep(0.5)

    return _summarize(all_events, days)


def _fetch_actuals(lat: float, lon: float, start: str, end: str) -> Optional[dict]:
    try:
        resp = requests.get(
            ARCHIVE_API,
            params={
                "latitude":  lat,
                "longitude": lon,
                "daily":     "temperature_2m_max,temperature_2m_min,precipitation_sum",
                "start_date": start,
                "end_date":   end,
                "timezone":   "UTC",
            },
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"Archive fetch ({lat},{lon}) failed: {e}")
        return None


def _simulate(data: dict, variable: str, threshold: float, comparison: str,
              city: str, label: str) -> list[dict]:
    """
    Simulate a rolling base-rate forecast for every day from day 14 onward.
    Forecast = fraction of the past 14 days that crossed the threshold.
    """
    daily  = data.get("daily", {})
    times  = daily.get("time", [])
    values = daily.get(variable, [])

    if not times or not values or len(times) != len(values):
        return []

    events = []
    window = 14

    for i in range(window, len(times)):
        window_vals = [values[j] for j in range(i - window, i) if values[j] is not None]
        if not window_vals:
            continue

        hits = sum(
            1 for v in window_vals
            if (comparison == "above" and v > threshold) or
               (comparison == "below" and v < threshold)
        )
        forecast_prob = hits / len(window_vals)

        actual_val = values[i]
        if actual_val is None:
            continue

        actual_hit = (comparison == "above" and actual_val > threshold) or \
                     (comparison == "below" and actual_val < threshold)

        events.append({
            "date":          times[i],
            "city":          city,
            "threshold":     label,
            "forecast_prob": round(forecast_prob, 3),
            "actual":        actual_hit,
            "actual_val":    actual_val,
        })

    return events


def _summarize(events: list[dict], days: int) -> dict:
    if not events:
        return _empty(days)

    bets: list[dict] = []
    correct = 0
    total_pnl = 0.0

    for e in events:
        prob   = e["forecast_prob"]
        actual = e["actual"]

        # Simulate: market priced at fair value (base rate itself)
        # Our signal vs a 50/50 naive market to measure directional skill
        if prob >= 0.5 + EDGE_MIN:
            signal = "BET"
        elif prob <= 0.5 - EDGE_MIN:
            signal = "FADE"
        else:
            continue

        bets.append(e)
        won = (signal == "BET" and actual) or (signal == "FADE" and not actual)
        if won:
            correct += 1
            total_pnl += 1.0
        else:
            total_pnl -= 1.0

    n_bets  = len(bets)
    win_rate = correct / n_bets if n_bets else 0.0

    avg_edge = (
        sum(abs(e["forecast_prob"] - 0.5) for e in bets) / n_bets
        if n_bets else 0.0
    )

    # Brier score (lower = better; random baseline = 0.25)
    brier = sum((e["forecast_prob"] - int(e["actual"])) ** 2 for e in events) / len(events)

    # Calibration: compare declared prob buckets to actual frequency
    calibration = _calibrate(events)

    return {
        "total_events":      len(events),
        "bets_placed":       n_bets,
        "win_rate":          round(win_rate, 3),
        "avg_edge_pct":      round(avg_edge * 100, 1),
        "total_pnl":         round(total_pnl, 2),
        "brier_score":       round(brier, 4),
        "backtest_days":     days,
        "cities_analyzed":   len(BACKTEST_CITIES),
        "calibration":       calibration,
    }


def _calibrate(events: list[dict]) -> list[dict]:
    """Bucket forecasts into deciles; compare avg predicted vs actual frequency."""
    buckets: dict[int, list] = {b: [] for b in range(0, 10)}
    for e in events:
        bucket = min(int(e["forecast_prob"] * 10), 9)
        buckets[bucket].append(int(e["actual"]))

    result = []
    for b, actuals in sorted(buckets.items()):
        if actuals:
            result.append({
                "bucket":    f"{b*10}–{b*10+10}%",
                "n":         len(actuals),
                "actual_pct": round(sum(actuals) / len(actuals) * 100, 1),
            })
    return result


def _empty(days: int) -> dict:
    return {
        "total_events":    0,
        "bets_placed":     0,
        "win_rate":        0.0,
        "avg_edge_pct":    0.0,
        "total_pnl":       0.0,
        "brier_score":     0.25,
        "backtest_days":   days,
        "cities_analyzed": 0,
        "calibration":     [],
    }
