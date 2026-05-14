import csv
import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

LOGS_DIR  = "logs"
CSV_PATH  = os.path.join(LOGS_DIR, "signals.csv")
JSON_PATH = os.path.join(LOGS_DIR, "signals.json")

_FIELDS = [
    "timestamp", "run_id", "market_id", "question", "city",
    "target_date", "metric", "threshold", "comparison",
    "ensemble_probability", "yes_votes", "total_votes",
    "polymarket_price", "kalshi_price", "best_platform", "market_yes_price",
    "edge_pct", "signal",
    "polymarket_url", "kalshi_url",
]


def log_signals(signals: list, run_id: str = "") -> None:
    os.makedirs(LOGS_DIR, exist_ok=True)
    if not signals:
        logger.info("No signals to log")
        return

    ts     = datetime.now(timezone.utc).isoformat(timespec="seconds")
    run_id = run_id or ts

    write_header = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        for sig in signals:
            writer.writerow({**sig, "timestamp": ts, "run_id": run_id})

    existing: list = []
    if os.path.exists(JSON_PATH):
        try:
            with open(JSON_PATH, encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing = []

    for sig in signals:
        # Flatten by_model dict to JSON string for storage
        row = {**sig, "timestamp": ts, "run_id": run_id}
        if isinstance(row.get("by_model"), dict):
            row["by_model"] = json.dumps(row["by_model"])
        existing.append(row)

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)

    logger.info(f"Logged {len(signals)} signals (run_id={run_id})")


def get_history(limit: int = 200) -> list:
    if not os.path.exists(JSON_PATH):
        return []
    try:
        with open(JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data[-limit:] if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"Error reading history: {e}")
        return []
