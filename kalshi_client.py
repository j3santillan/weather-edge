"""Kalshi weather market client — RSA key-pair authentication.

Fetches weather markets by querying known weather series tickers directly.
Prices come back in _dollars fields (already 0–1 scale).

Auth: RSA-PKCS1v15-SHA256 signed requests.
  Signature = RSA-SHA256( "{timestamp_ms}{METHOD}/trade-api/v2{path}" )
  Headers:
    KALSHI-ACCESS-KEY:       <key_id from dashboard>
    KALSHI-ACCESS-SIGNATURE: <base64 signature>
    KALSHI-ACCESS-TIMESTAMP: <millisecond unix timestamp as string>
"""
import base64
import logging
import os
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

KALSHI_API = "https://api.elections.kalshi.com/trade-api/v2"
API_PATH   = "/trade-api/v2"

# Known Kalshi weather series tickers (temperature, rain, snow, hurricane)
WEATHER_SERIES = [
    # Temperature — high temp by city
    "KXHIGHNY", "KXHIGHCHI", "KXHIGHMIA", "KXHIGHLAX",
    "KXHIGHTBOS", "KXHIGHTDAL", "KXHIGHTHOU", "KXHIGHTSEA",
    "KXHIGHTSFO", "KXHIGHTOKC", "KXHIGHTPHX", "KXHIGHTHATL",
    "KXHIGHTDEN", "KXCITIESWEATHER",
    "HIGHMIA", "HIGHNY", "HIGHCHI", "HIGHAUS",
    # Rain — monthly/daily by city
    "KXRAINNY", "KXRAINNYC", "RAINNYC",
    "KXRAINHOU", "RAINHOU",
    "KXRAINSEA", "RAINSEA",
    "KXRAINNO",  "RAINNO",
    "KXRAINMIAM", "KXRAINCHIM", "KXRAINAUSM",
    "KXRAINDENM", "KXRAINSFOM", "KXRAINSEAM",
    "KXRAINDALM", "KXRAINHOUM", "KXRAINLAXM",
    # Snow
    "KXASPSNOWM", "KXBOSSNOWM", "KXCHISNOWM",
    "KXDALSNOWM", "KXDENSNOWM", "KXDETSNOWM",
    "KXKCISNOWM", "KXMSPSNOWM", "KXNYCSNOWM",
    "KXPHISNOWM", "KXSLCSNOWM",
    # Hurricane / tropical
    "KXHURCAT", "KXHURCTOT",
    "KXHURPATHFLA", "KXHURPATHGULFCOAST",
]


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _load_private_key():
    key_file = os.environ.get("KALSHI_KEY_FILE", "kalshi_private_key.pem")
    if not os.path.exists(key_file):
        return None
    try:
        from cryptography.hazmat.primitives import serialization
        with open(key_file, "rb") as f:
            pem = f.read()
        return serialization.load_pem_private_key(pem, password=None)
    except Exception as e:
        logger.warning(f"Kalshi: could not load private key: {e}")
        return None


def _sign_headers(method: str, path: str) -> Optional[dict]:
    key_id = os.environ.get("KALSHI_KEY_ID", "").strip()
    if not key_id:
        return None
    private_key = _load_private_key()
    if private_key is None:
        return None
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        ts  = str(int(time.time() * 1000))
        msg = f"{ts}{method.upper()}{API_PATH}{path}"
        sig = private_key.sign(msg.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
        return {
            "KALSHI-ACCESS-KEY":       key_id,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
            "KALSHI-ACCESS-TIMESTAMP": ts,
            "Accept":                  "application/json",
            "Content-Type":            "application/json",
        }
    except Exception as e:
        logger.warning(f"Kalshi: signature generation failed: {e}")
        return None


def _auth_available() -> bool:
    return bool(
        os.environ.get("KALSHI_KEY_ID", "").strip() and
        os.path.exists(os.environ.get("KALSHI_KEY_FILE", "kalshi_private_key.pem"))
    )


# ── Fetch one series ───────────────────────────────────────────────────────────

def _fetch_series(series_ticker: str) -> list[dict]:
    """Return all open markets for a single series ticker."""
    path   = "/markets"
    cursor = None
    result = []

    while True:
        headers = _sign_headers("GET", path)
        if not headers:
            return []

        params: dict = {
            "series_ticker": series_ticker,
            "status":        "open",
            "limit":         200,
        }
        if cursor:
            params["cursor"] = cursor

        try:
            resp = requests.get(
                f"{KALSHI_API}{path}",
                params=params,
                headers=headers,
                timeout=15,
            )
            if resp.status_code == 404:
                return []  # series doesn't exist
            if resp.status_code == 429:
                logger.debug(f"Kalshi 429 on {series_ticker} — backing off 2s")
                time.sleep(2)
                continue
            if resp.status_code == 401:
                logger.warning("Kalshi: 401 Unauthorized — check KALSHI_KEY_ID")
                return []
            resp.raise_for_status()
            data = resp.json()
        except requests.HTTPError as e:
            logger.warning(f"Kalshi HTTP error series={series_ticker}: {e}")
            return result
        except Exception as e:
            logger.debug(f"Kalshi fetch series={series_ticker} failed: {e}")
            return result

        batch  = data.get("markets", [])
        result.extend(batch)
        cursor = data.get("cursor")
        if not cursor or not batch:
            break

    return result


# ── Market parsing ─────────────────────────────────────────────────────────────

def _parse(raw: dict) -> Optional[dict]:
    try:
        ticker       = (raw.get("ticker") or "").strip()
        event_ticker = (raw.get("event_ticker") or "").strip()
        title        = (raw.get("title") or "").strip()
        if not title:
            return None

        # Prices already 0–1 (dollar units, not cents)
        yes_bid = _safe_float(raw.get("yes_bid_dollars"))
        yes_ask = _safe_float(raw.get("yes_ask_dollars"))

        if yes_bid is not None and yes_ask is not None:
            yes_price = (yes_bid + yes_ask) / 2
        elif yes_bid is not None:
            yes_price = yes_bid
        elif yes_ask is not None:
            yes_price = yes_ask
        else:
            last = _safe_float(raw.get("last_price_dollars"))
            yes_price = last if last is not None else 0.5

        yes_price = round(max(0.01, min(0.99, yes_price)), 3)

        return {
            "id":         ticker,
            "question":   title,
            "yes_price":  yes_price,
            "no_price":   round(1 - yes_price, 3),
            "volume":     _safe_float(raw.get("volume_fp")) or 0.0,
            "close_time": raw.get("close_time", ""),
            "url":        f"https://kalshi.com/markets/{event_ticker}" if event_ticker else (f"https://kalshi.com/markets/{ticker}" if ticker else ""),
            "source":     "kalshi",
        }
    except Exception as e:
        logger.debug(f"Kalshi parse error: {e}")
        return None


def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def get_weather_markets(series_list: Optional[list[str]] = None) -> list:
    """Fetch open weather markets from Kalshi by querying known weather series tickers."""
    if not _auth_available():
        logger.warning(
            "Kalshi: KALSHI_KEY_ID not set in .env — skipping Kalshi markets. "
            "Add your Key ID from https://kalshi.com/profile/api-keys"
        )
        return []

    tickers = series_list or WEATHER_SERIES
    markets: list[dict] = []
    seen:    set[str]   = set()

    for i, series_ticker in enumerate(tickers):
        raw_list = _fetch_series(series_ticker)
        new_count = 0
        for raw in raw_list:
            mid = raw.get("ticker", "")
            if mid and mid not in seen:
                seen.add(mid)
                parsed = _parse(raw)
                if parsed:
                    markets.append(parsed)
                    new_count += 1

        if new_count:
            logger.debug(f"Kalshi: {series_ticker} → {new_count} markets")

        # Rate limit — avoid 429s; skip final sleep
        if i < len(tickers) - 1:
            time.sleep(0.3)

    markets.sort(key=lambda m: m["volume"], reverse=True)
    logger.info(f"Kalshi: {len(markets)} weather markets from {len(tickers)} series")
    return markets
