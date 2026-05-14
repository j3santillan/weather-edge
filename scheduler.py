"""Run weather-edge at 6:00 AM Eastern Time every day. Fires immediately on start."""
import logging
import os
import sys
from datetime import datetime

import pytz

os.makedirs("logs", exist_ok=True)
os.makedirs("output", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/scheduler.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from main import run

ET = pytz.timezone("America/New_York")


def main() -> None:
    logger.info("Weather Edge scheduler starting — runs daily at 06:00 ET")

    scheduler = BlockingScheduler(timezone=ET)
    scheduler.add_job(
        run,
        trigger=CronTrigger(hour=6, minute=0, timezone=ET),
        next_run_time=datetime.now(ET),   # fire immediately on start
        id="weather_edge",
        name="Weather Edge Analysis",
        misfire_grace_time=600,
        coalesce=True,
    )

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    main()
