"""
Lightweight in-process scheduler -- runs the collector and background
maintenance on configurable intervals, no external cron/service
required (though Task Scheduler/cron remain valid alternatives, see
scripts/setup_task_scheduler.bat).

Configure via .env:
    COLLECTOR_INTERVAL_MINUTES=15
    MAINTENANCE_INTERVAL_MINUTES=360
    DAILY_DIGEST_HOUR=8       (0-23, local time)
    WEEKLY_DIGEST_DAY=monday

Usage: python -m scripts.scheduler
"""
import os
import logging

import schedule
import time

import app.env  # noqa: F401
from collectors.runner import run as run_collector
from collectors.self_maintain import run_self_maintenance
from app.alerts import send_digests

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("scheduler")


def job_collect():
    logger.info("Scheduled collector run starting")
    run_collector(notify=False)


def job_maintain():
    logger.info("Scheduled maintenance run starting")
    run_self_maintenance()


def job_daily_digest():
    send_digests("daily")


def job_weekly_digest():
    send_digests("weekly")


def job_instant_digest():
    send_digests("instant")


if __name__ == "__main__":
    collector_minutes = int(os.getenv("COLLECTOR_INTERVAL_MINUTES", "15"))
    maintenance_minutes = int(os.getenv("MAINTENANCE_INTERVAL_MINUTES", "360"))
    daily_hour = os.getenv("DAILY_DIGEST_HOUR", "08:00")
    weekly_day = os.getenv("WEEKLY_DIGEST_DAY", "monday").lower()

    schedule.every(collector_minutes).minutes.do(job_collect)
    schedule.every(maintenance_minutes).minutes.do(job_maintain)
    schedule.every(15).minutes.do(job_instant_digest)
    schedule.every().day.at(daily_hour).do(job_daily_digest)
    getattr(schedule.every(), weekly_day).at(daily_hour).do(job_weekly_digest)

    logger.info("Scheduler started: collector every %dmin, maintenance every %dmin", collector_minutes, maintenance_minutes)
    while True:
        schedule.run_pending()
        time.sleep(5)
