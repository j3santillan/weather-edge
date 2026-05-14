"""Four-model ensemble forecast client via Open-Meteo Ensemble API.

Model mapping:
  ECMWF → ecmwf_ifs04    (~51 members)
  GFS   → gfs025          (~31 members)
  NAM   → icon_seamless   (~40 members, ICON is closest to NAM resolution)
  GEM   → gem_global      (~20 members, Canadian GEM; ukmet_seamless not on OM ensemble API)
  Total  ≈ 140+ members
"""
import logging
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

ENSEMBLE_API = "https://ensemble-api.open-meteo.com/v1/ensemble"

MODELS: dict[str, dict] = {
    "ECMWF": {"id": "ecmwf_ifs04",              "hourly": "temperature_2m,precipitation,windspeed_10m", "days": 7},
    "GFS":   {"id": "gfs025",                   "hourly": "temperature_2m,precipitation,windspeed_10m", "days": 7},
    "NAM":   {"id": "icon_seamless",             "hourly": "temperature_2m,precipitation,windspeed_10m", "days": 7},
    "GEM":   {"id": "gem_global",               "hourly": "temperature_2m,precipitation,windspeed_10m", "days": 7},
}

_cache: dict[str, dict] = {}


def get_ensemble(city: str, lat: float, lon: float) -> Optional[dict]:
    """
    Fetch all ensemble members for a city from 4 models.
    Returns {model_name: {time: [...], members: {var_memberXX: [...]}}}
    Cached in memory so the same city is only fetched once per run.
    """
    if city in _cache:
        return _cache[city]

    result: dict[str, dict] = {}
    for model_name, cfg in MODELS.items():
        data = _fetch_model(model_name, cfg, lat, lon)
        if data:
            result[model_name] = data
        time.sleep(0.4)

    if not result:
        logger.warning(f"  No ensemble data returned for {city}")
        return None

    n_temp = sum(
        len([k for k in m["members"] if k.startswith("temperature_2m_member")])
        for m in result.values()
    )
    logger.info(f"  {city}: {len(result)}/4 models, ~{n_temp} temp members total")
    _cache[city] = result
    return result


def get_member_count(ensemble_data: dict) -> int:
    """Return total number of temperature ensemble members across all models."""
    return sum(
        len([k for k in m["members"] if k.startswith("temperature_2m_member")])
        for m in ensemble_data.values()
    )


def _fetch_model(model_name: str, cfg: dict, lat: float, lon: float) -> Optional[dict]:
    try:
        resp = requests.get(
            ENSEMBLE_API,
            params={
                "latitude":      lat,
                "longitude":     lon,
                "hourly":        cfg["hourly"],
                "models":        cfg["id"],
                "forecast_days": cfg["days"],
                "timezone":      "UTC",
            },
            timeout=25,
        )
        resp.raise_for_status()
        hourly = resp.json().get("hourly", {})
        times = hourly.pop("time", [])
        if not times:
            logger.warning(f"  {model_name} returned empty time series")
            return None
        return {"time": times, "members": hourly}
    except Exception as e:
        logger.warning(f"  Ensemble {model_name} ({cfg['id']}) failed: {e}")
        return None
