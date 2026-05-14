"""Ensemble vote-counting probability engine with bias correction.

For each ensemble member:
  1. Extract the target date's hourly values
  2. Aggregate to daily (max for temp/wind, sum for precip)
  3. Subtract per-model bias correction
  4. Cast yes/no vote on whether threshold is crossed
Probability = yes_votes / total_votes
"""
import logging

logger = logging.getLogger(__name__)

# Which member keys to look for per metric
_MEMBER_PREFIX = {
    "temperature_2m": "temperature_2m_member",
    "precipitation":  "precipitation_member",
    "windspeed_10m":  "windspeed_10m_member",
}

# How to collapse 24 hourly values into one daily value
_AGGREGATE = {
    "temperature_2m": max,
    "precipitation":  sum,
    "windspeed_10m":  max,
}


def compute_probability(
    ensemble_data:  dict,
    metric:         str,
    threshold:      float,
    comparison:     str,   # "above" | "below"
    target_date:    str,   # "YYYY-MM-DD"
    bias_corrections: dict,  # {model: float}  value to subtract from each forecast
) -> dict:
    """
    Count what % of all ensemble members predict the threshold will be hit.

    Returns:
        {
          "probability":  float,
          "yes_votes":    int,
          "total_votes":  int,
          "by_model":     {model: {votes, total, probability, avg_forecast, bias_applied}}
        }
    """
    if not target_date:
        return _empty()

    prefix = _MEMBER_PREFIX.get(metric, "temperature_2m_member")
    agg_fn = _AGGREGATE.get(metric, max)

    total_yes = 0
    total_all = 0
    by_model:  dict[str, dict] = {}

    for model_name, model_data in ensemble_data.items():
        times   = model_data.get("time", [])
        members = model_data.get("members", {})
        bias    = bias_corrections.get(model_name, 0.0)

        # Indices for the target calendar day
        day_indices = [i for i, t in enumerate(times) if t[:10] == target_date]
        if not day_indices:
            logger.debug(f"  {model_name}: no hours found for {target_date}")
            continue

        member_keys = [k for k in members if k.startswith(prefix)]
        if not member_keys:
            logger.debug(f"  {model_name}: no '{prefix}*' keys")
            continue

        model_yes = 0
        model_all = 0
        day_agg_vals: list[float] = []

        for key in member_keys:
            vals = members[key]
            hourly = [vals[i] for i in day_indices if i < len(vals) and vals[i] is not None]
            if not hourly:
                continue

            day_val = agg_fn(hourly) - bias
            day_agg_vals.append(day_val)

            hit = (comparison == "above" and day_val > threshold) or \
                  (comparison == "below" and day_val < threshold)
            if hit:
                model_yes += 1
            model_all += 1

        if model_all == 0:
            continue

        avg_val = sum(day_agg_vals) / len(day_agg_vals) if day_agg_vals else None
        by_model[model_name] = {
            "votes":        model_yes,
            "total":        model_all,
            "probability":  round(model_yes / model_all, 3),
            "avg_forecast": round(avg_val, 1) if avg_val is not None else None,
            "bias_applied": round(bias, 3),
        }
        total_yes += model_yes
        total_all += model_all

    if total_all == 0:
        return _empty()

    return {
        "probability": round(total_yes / total_all, 3),
        "yes_votes":   total_yes,
        "total_votes": total_all,
        "by_model":    by_model,
    }


def _empty() -> dict:
    return {"probability": 0.0, "yes_votes": 0, "total_votes": 0, "by_model": {}}
