import json
import logging
import re

import anthropic

logger = logging.getLogger(__name__)
client = anthropic.Anthropic()

# Cached: stable analysis instructions
_SYSTEM_PROMPT = """You are a quantitative analyst specializing in weather prediction markets.

You receive NOAA/NWS 7-day forecast data for major US cities and active Polymarket weather markets.

Your task: identify mispriced markets where NOAA data clearly diverges from market-implied probability.

Method:
1. Match each market question to relevant NOAA city/period data
2. Estimate the true Yes probability from NOAA (use precipitation probability directly when available; \
for temperature markets, compare forecast temp to the threshold in the question)
3. Edge = forecast_yes_probability - market_yes_price (positive = Yes underpriced)
4. Signal rules:
   - |edge| < 0.08  → SKIP (noise)
   - edge >= +0.08  → BET (Yes underpriced, buy Yes)
   - edge <= -0.08  → FADE (Yes overpriced, buy No)

Be conservative. Skip markets where you cannot match forecast data with confidence.
Prefer markets with clear quantitative matches (precipitation %, temperature vs threshold).

Return ONLY a valid JSON array — no prose before or after. Each element:
{
  "market_id": "string",
  "question": "string",
  "city": "string",
  "relevant_period": "string",
  "market_yes_price": float,
  "forecast_yes_probability": float,
  "edge_pct": float,
  "signal": "BET"|"FADE"|"SKIP",
  "reasoning": "1-2 sentences citing specific NOAA figures"
}"""


def analyze(forecasts: dict, markets: list) -> list:
    if not markets:
        logger.info("No markets to analyze")
        return []

    forecast_json = json.dumps(forecasts, indent=2)
    markets_json = json.dumps(markets, indent=2)

    # Trim to stay within token budget
    if len(forecast_json) > 14000:
        forecast_json = forecast_json[:14000] + "\n...(truncated)"
    if len(markets_json) > 8000:
        markets_json = markets_json[:8000] + "\n...(truncated)"

    user_content = (
        f"## NOAA Forecast Data\n\n{forecast_json}\n\n"
        f"## Polymarket Weather Markets\n\n{markets_json}\n\n"
        "Return the JSON signal array."
    )

    try:
        msg = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=4096,
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},  # Cache stable instructions
                }
            ],
            messages=[{"role": "user", "content": user_content}],
        )

        text = msg.content[0].text.strip()
        logger.info(
            f"Analysis done | in:{msg.usage.input_tokens} out:{msg.usage.output_tokens} "
            f"cache_read:{getattr(msg.usage, 'cache_read_input_tokens', 0)}"
        )

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\[.*\]", text, re.DOTALL)
            if match:
                return json.loads(match.group())
            logger.error("Could not parse Claude response as JSON")
            logger.debug(f"Raw response: {text[:500]}")
            return []

    except anthropic.APIError as e:
        logger.error(f"Anthropic API error: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected analysis error: {e}")
        return []
