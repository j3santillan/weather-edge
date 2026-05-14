import json
import logging
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

GAMMA_API = "https://gamma-api.polymarket.com"

WEATHER_KEYWORDS = [
    "rain", "snow", "temperature", "hurricane", "storm",
    "precipitation", "weather", "blizzard", "tornado", "flood",
    "drought", "heat", "cold", "wind", "degrees", "precip",
]


def _is_weather_market(question: str) -> bool:
    q = question.lower()
    return any(kw in q for kw in WEATHER_KEYWORDS)


def _fetch_page(offset: int, limit: int = 100) -> list:
    try:
        resp = requests.get(
            f"{GAMMA_API}/markets",
            params={
                "active": "true",
                "closed": "false",
                "limit": limit,
                "offset": offset,
                "order": "volume",      # volume ordering exposes weather markets
                "ascending": "false",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.debug(f"Page fetch offset={offset} failed: {e}")
        return []


def _parse_market(raw: dict) -> Optional[dict]:
    try:
        question = raw.get("question", "").strip()
        if not question:
            return None

        outcomes_raw = raw.get("outcomes", "[]")
        outcomes = json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else outcomes_raw

        prices_raw = raw.get("outcomePrices", "[]")
        prices_str = json.loads(prices_raw) if isinstance(prices_raw, str) else prices_raw
        prices = [float(p) for p in prices_str]

        if len(outcomes) < 2 or len(prices) < 2:
            return None

        market_slug = raw.get("slug", "")
        events = raw.get("events", [])
        event_slug = events[0].get("slug", "") if events else ""

        if event_slug and market_slug:
            url = f"https://polymarket.com/event/{event_slug}/{market_slug}"
        elif event_slug:
            url = f"https://polymarket.com/event/{event_slug}"
        else:
            url = f"https://polymarket.com/event/{market_slug}" if market_slug else ""

        return {
            "id": raw.get("id", ""),
            "question": question,
            "outcomes": outcomes,
            "prices": prices,
            "yes_price": prices[0],
            "no_price": prices[1],
            "volume": float(raw.get("volume") or 0),
            "liquidity": float(raw.get("liquidity") or 0),
            "end_date": raw.get("endDate", ""),
            "url": url,
        }
    except Exception as e:
        logger.debug(f"Parse error for market {raw.get('id')}: {e}")
        return None


def get_weather_markets(max_pages: int = 20) -> list:
    """Paginate Polymarket markets and filter for weather-related questions."""
    seen: set[str] = set()
    markets: list[dict] = []

    for page in range(max_pages):
        offset = page * 100
        raw_page = _fetch_page(offset)
        if not raw_page:
            break

        for raw in raw_page:
            question = raw.get("question", "")
            if not _is_weather_market(question):
                continue
            mid = raw.get("id", "")
            if mid and mid not in seen:
                seen.add(mid)
                parsed = _parse_market(raw)
                if parsed:
                    markets.append(parsed)

        time.sleep(0.25)

    markets.sort(key=lambda m: m["volume"], reverse=True)
    logger.info(f"Found {len(markets)} weather markets on Polymarket (scanned {max_pages} pages)")
    return markets


def extract_cities_from_markets(markets: list) -> set[str]:
    """Pull city names out of market question strings for dynamic forecast fetching."""
    import re
    # Captures city name between "in " and the next verb/preposition
    # e.g. "temperature in Buenos Aires be" → "Buenos Aires"
    # No IGNORECASE so [A-Z] only matches uppercase — prevents "be" from being captured
    pattern = re.compile(
        r"(?i:temperature|rainfall|snowfall|weather)\s+in\s+"
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)"
        r"(?=\s+(?:be|to|on|by|exceed|reach|above|below|between|higher|lower|\d))"
    )
    cities: set[str] = set()
    for m in markets:
        match = pattern.search(m.get("question", ""))
        if match:
            cities.add(match.group(1).strip())
    return cities
