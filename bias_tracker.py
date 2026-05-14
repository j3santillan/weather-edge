"""Tracks per-model, per-city, per-season forecast bias in data/bias.json."""
import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

DATA_DIR = "data"
BIAS_FILE = os.path.join(DATA_DIR, "bias.json")

_SEASON = {12: "winter", 1: "winter",  2: "winter",
           3:  "spring",  4: "spring",  5: "spring",
           6:  "summer",  7: "summer",  8: "summer",
           9:  "autumn", 10: "autumn", 11: "autumn"}


def _season() -> str:
    return _SEASON[datetime.now().month]


def _load() -> dict:
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(BIAS_FILE):
        return {}
    try:
        with open(BIAS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(BIAS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_corrections(city: str) -> dict:
    """Return {model: mean_bias} for the 4 ensemble models, current season."""
    data = _load()
    season = _season()
    result = {}
    for model in ("ECMWF", "GFS", "NAM", "GEM"):
        key = f"{model}:{city}:{season}"
        errors = data.get(key, {}).get("errors", [])
        result[model] = round(sum(errors) / len(errors), 3) if errors else 0.0
    return result


def get_all_corrections() -> dict:
    """Return full bias data dict (for dashboard display)."""
    return _load()


def record_error(model: str, city: str, predicted: float, actual: float) -> None:
    """Record a forecast error; keeps last 90 per model/city/season key."""
    data = _load()
    season = _season()
    key = f"{model}:{city}:{season}"
    entry = data.setdefault(key, {"errors": [], "n": 0})
    entry["errors"].append(round(predicted - actual, 3))
    entry["errors"] = entry["errors"][-90:]
    entry["n"] = len(entry["errors"])
    _save(data)
    logger.debug(f"Bias recorded: {key} error={predicted - actual:.3f}")
