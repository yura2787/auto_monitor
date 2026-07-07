from celery import Celery
from celery.schedules import crontab

from config.settings import settings

celery_app = Celery(
    "auto_monitor",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["tasks.monitor"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Kyiv",
    enable_utc=True,
    beat_schedule={
        # runs every CHECK_INTERVAL seconds (default 120)
        "monitor-filters": {
            "task": "tasks.monitor.monitor_filters",
            "schedule": settings.CHECK_INTERVAL,
        },
        # sends daily stats to every user at DAILY_STATS_HOUR:00
        "daily-stats": {
            "task": "tasks.monitor.daily_stats",
            "schedule": crontab(hour=settings.DAILY_STATS_HOUR, minute=0),
        },
        # removes old listings every Monday at 03:00
        "cleanup-old-listings": {
            "task": "tasks.monitor.cleanup_old_listings",
            "schedule": crontab(hour=3, minute=0, day_of_week=1),
        },
    },
)
