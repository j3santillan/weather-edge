"""Claude-powered market question parser.

Converts natural-language market questions (Polymarket / Kalshi) into structured
{city, metric, threshold_value, comparison, target_date} records that the
probability engine can consume.

Claude only does entity extraction — probability calculation is done by
probability_engine.py using raw ensemble vote counts.
"""
import json
import logging
import re

import anthropic

logger = logging.getLogger(__name__)
_client = anthropic.Anthropic()

_SYSTEM = """You are a structured data extractor for weather prediction markets.

Parse each market question into the following JSON fields. Always convert to metric units.

Fields:
  city            string  — city name only (e.g. "Miami", "Chicago"). null if unclear.
  metric          string  — one of: "temperature_2m", "precipitation", "windspeed_10m"
  threshold_value float   — numeric threshold in METRIC units:
                            °C for temperature (convert from °F: (F-32)×5/9)
                            mm for precipitation (convert from inches: ×25.4)
                            km/h for wind (convert from mph: ×1.609)
  comparison      string  — "above" or "below"
  target_date     string  — best estimate as YYYY-MM-DD; use end_date from the market if provided

If a market cannot be reliably parsed (no city, no numeric threshold, too ambiguous),
set city to null — these will be skipped.

Return ONLY a valid JSON array, one object per input market, same order, no prose.
Include the market_id field from the input in each output object.

Example output:
[
  {
    "market_id": "abc123",
    "city": "Miami",
    "metric": "precipitation",
    "threshold_value": 5.08,
    "comparison": "above",
    "target_date": "2026-05-15"
  }
]"""


def _parse_json_robust(text: str) -> list:
    """
    Parse a JSON array from text, handling truncated responses gracefully.
    Falls back to extracting individual complete JSON objects if the array is cut off.
    """
    # 1. Try full parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Try regex for a complete array
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # 3. Extract individual complete objects from truncated output
    objects: list = []
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                try:
                    objects.append(json.loads(text[start : i + 1]))
                except json.JSONDecodeError:
                    pass
                start = -1

    if objects:
        logger.warning(f"JSON truncated — recovered {len(objects)} objects from partial response")
    return objects


def parse_markets(markets: list) -> list:
    """
    Parse a list of merged market dicts with Claude.
    Adds city/metric/threshold/comparison/target_date fields to each market dict.
    Returns the original list with parsed fields merged in.
    """
    if not markets:
        return []

    input_payload = [
        {
            "market_id": m.get("id", ""),
            "question":  m.get("question", ""),
            "end_date":  m.get("end_date") or m.get("close_time", ""),
        }
        for m in markets
    ]

    payload_json = json.dumps(input_payload, indent=2)
    if len(payload_json) > 12000:
        payload_json = payload_json[:12000] + "\n...(truncated)"

    try:
        msg = _client.messages.create(
            model="claude-opus-4-7",
            max_tokens=8192,
            system=[
                {
                    "type":          "text",
                    "text":          _SYSTEM,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role":    "user",
                    "content": f"Parse these {len(input_payload)} markets:\n\n{payload_json}",
                }
            ],
        )

        logger.info(
            f"Market parse | in:{msg.usage.input_tokens} "
            f"out:{msg.usage.output_tokens} "
            f"cache_read:{getattr(msg.usage, 'cache_read_input_tokens', 0)} "
            f"stop:{msg.stop_reason}"
        )

        text = msg.content[0].text.strip()
        parsed_list = _parse_json_robust(text)

        # Index by market_id for O(1) merge
        parsed_by_id = {
            p["market_id"]: p
            for p in parsed_list
            if isinstance(p, dict) and p.get("market_id")
        }

        result = []
        parseable = 0
        for mkt in markets:
            mid    = mkt.get("id", "")
            parsed = parsed_by_id.get(mid, {})
            merged = {**mkt, **parsed}
            if merged.get("city") and merged.get("metric"):
                parseable += 1
            result.append(merged)

        logger.info(f"  {parseable}/{len(markets)} markets fully parsed (city + metric)")
        return result

    except anthropic.APIError as e:
        logger.error(f"Anthropic API error in market_parser: {e}")
        return markets
    except Exception as e:
        logger.error(f"Market parser unexpected error: {e}")
        return markets
