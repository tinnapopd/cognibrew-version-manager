"""
1. Pull bundle from sync server
2. Send face-update events to RabbitMQ using pagination
3. Apply similarity threshold to update recognition service containers
"""

import time

import schedule

from core.config import settings
from core.logger import Logger
from processors.pull_processor import pull_bundle
from processors.upgrade_processor import apply_threshold

logger = Logger().get_logger()


def run_sync_task():
    logger.info("Starting scheduled sync task...")
    try:
        similarity_threshold = pull_bundle()
        apply_threshold(similarity_threshold)
        logger.info("Task completed successfully.")
    except Exception as e:
        logger.error(f"Task failed: {e}")


if __name__ == "__main__":
    schedule.every().day.at(settings.sync.SCHEDULE_TIME).do(run_sync_task)
    while True:
        schedule.run_pending()
        time.sleep(settings.sync.CHECK_EVERY)
