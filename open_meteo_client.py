"""Open-Meteo client for international city forecasts (no API key required)."""
import logging
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

GEO_API = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_API = "https://api.open-meteo.com/v1/forecast"

_geo_cache: dict[str, Optional[dict]] = {}


def geocode(city: str) -> Optional[dict]:
    if city in _geo_cache:
        return _geo_cache[city]

    try:
        resp = requests.get(GEO_API, params={"name": city, "count": 1, "language": "en"}, timeout=10)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if results:
            r = results[0]
            coord = {"lat": r["latitude"], "lon": r["longitude"], "name": r["name"], "country": r.get("country", "")}
            _geo_cache[city] = coord
            return coord
    except Exception as e:
        logger.debug(f"Geocode failed for '{city}': {e}")

    _geo_cache[city] = None
    return None


def get_forecast(city: str) -> Optional[dict]:
    coord = geocode(city)
    if not coord:
        return None

    try:
        resp = requests.get(
            FORECAST_API,
            params={
                "latitude": coord["lat"],
                "longitude": coord["lon"],
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,windspeed_10m_max",
                "timezone": "auto",
                "forecast_days": 7,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        daily = data.get("daily", {})
        times = daily.get("time", [])

        periods = []
        for i, date in enumerate(times):
            periods.append({
                "date": date,
                "temperature_max_c": (daily.get("temperature_2m_max") or [None])[i],
                "temperature_min_c": (daily.get("temperature_2m_min") or [None])[i],
                "precipitation_sum_mm": (daily.get("precipitation_sum") or [None])[i],
                "precipitation_probability_pct": (daily.get("precipitation_probability_max") or [None])[i],
                "windspeed_max_kph": (daily.get("windspeed_10m_max") or [None])[i],
            })

        return {
            "city": city,
            "resolved_name": f"{coord['name']}, {coord['country']}",
            "source": "open-meteo",
            "periods": periods,
        }
    except Exception as e:
        logger.error(f"Open-Meteo forecast failed for '{city}': {e}")
        return None


def get_forecasts_for_cities(cities: set[str]) -> dict:
    results = {}
    for city in cities:
        logger.info(f"  Fetching Open-Meteo for {city}...")
        forecast = get_forecast(city)
        if forecast:
            results[city] = forecast
        time.sleep(0.5)
    return results
