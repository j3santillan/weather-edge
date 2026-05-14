import logging
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "weather-edge/1.0 (github.com/weather-edge)",
    "Accept": "application/geo+json",
}

MAJOR_CITIES: dict[str, tuple[float, float]] = {
    "New York":      (40.7128, -74.0060),
    "Los Angeles":   (34.0522, -118.2437),
    "Chicago":       (41.8781, -87.6298),
    "Houston":       (29.7604, -95.3698),
    "Miami":         (25.7617, -80.1918),
    "Seattle":       (47.6062, -122.3321),
    "Denver":        (39.7392, -104.9903),
    "Dallas":        (32.7767, -96.7970),
    "Atlanta":       (33.7490, -84.3880),
    "Boston":        (42.3601, -71.0589),
}


def get_forecast(city: str) -> Optional[dict]:
    coords = MAJOR_CITIES.get(city)
    if not coords:
        return None

    lat, lon = coords
    try:
        resp = requests.get(
            f"https://api.weather.gov/points/{lat},{lon}",
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        props = resp.json()["properties"]

        rel = props.get("relativeLocation", {}).get("properties", {})
        resolved = f"{rel.get('city', city)}, {rel.get('state', '')}".strip(", ")

        time.sleep(0.5)
        resp = requests.get(props["forecast"], headers=HEADERS, timeout=15)
        resp.raise_for_status()
        periods = resp.json()["properties"]["periods"]

        return {
            "city": city,
            "resolved_name": resolved,
            "periods": [
                {
                    "name": p["name"],
                    "temperature": p["temperature"],
                    "temperatureUnit": p["temperatureUnit"],
                    "windSpeed": p["windSpeed"],
                    "windDirection": p["windDirection"],
                    "shortForecast": p["shortForecast"],
                    "detailedForecast": p["detailedForecast"],
                    "probabilityOfPrecipitation": (
                        p.get("probabilityOfPrecipitation") or {}
                    ).get("value"),
                    "isDaytime": p["isDaytime"],
                    "startTime": p["startTime"],
                }
                for p in periods[:8]
            ],
        }
    except requests.HTTPError as e:
        logger.error(f"HTTP {e.response.status_code} for {city}: {e}")
    except Exception as e:
        logger.error(f"Error fetching {city}: {e}")
    return None


def get_all_forecasts() -> dict:
    results = {}
    for city in MAJOR_CITIES:
        logger.info(f"  Fetching {city}...")
        forecast = get_forecast(city)
        if forecast:
            results[city] = forecast
        time.sleep(1.0)
    logger.info(f"Fetched {len(results)}/{len(MAJOR_CITIES)} city forecasts")
    return results
