"""
APScheduler-based daily cron for the Flood Prediction system.
Runs predictions for all 367 stations at 6:00 AM IST every day.

Integrated into FastAPI via BackgroundScheduler (non-blocking).
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

_scheduler: BackgroundScheduler | None = None


def start_scheduler():
    """Start the daily prediction scheduler (6:00 AM IST)."""
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        print("⚠️  Scheduler already running.")
        return

    from prediction_service import sync_historical_predictions

    ist = pytz.timezone("Asia/Kolkata")
    _scheduler = BackgroundScheduler(timezone=ist)
    _scheduler.add_job(
        sync_historical_predictions,
        trigger=CronTrigger(hour=6, minute=0, timezone=ist),
        id="daily_flood_predictions",
        name="Daily Flood Auto-Sync",
        replace_existing=True,
    )
    _scheduler.start()
    print("⏰ Scheduler started: daily predictions at 6:00 AM IST")


def stop_scheduler():
    """Shutdown the scheduler gracefully."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        print("⏰ Scheduler stopped.")
        _scheduler = None


def get_scheduler():
    """Get the scheduler instance."""
    return _scheduler
