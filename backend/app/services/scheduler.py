"""
Scheduler: a lightweight background loop that promotes jobs whose `run_at`
(delayed / one-off scheduled / retry backoff) has arrived from `scheduled`
to `queued`, where the worker pool's claim query will then pick them up.

Kept separate from the worker pool because its job is fundamentally
different (time-based promotion, not execution) - this separation of
concerns is what the assignment calls the "Scheduler Service".
"""
import asyncio
import logging
from datetime import datetime, timezone

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.models import Job, JobStatus

logger = logging.getLogger("scheduler")


async def _promote_due_jobs():
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        due_jobs = (
            db.query(Job)
            .filter(Job.status == JobStatus.scheduled)
            .filter(Job.run_at.isnot(None))
            .filter(Job.run_at <= now)
            .all()
        )
        for job in due_jobs:
            job.status = JobStatus.queued
        if due_jobs:
            db.commit()
            logger.info("Promoted %d job(s) to queued", len(due_jobs))
    finally:
        db.close()


class SchedulerService:
    def __init__(self):
        self._stopping = asyncio.Event()
        self._task: asyncio.Task | None = None

    async def _loop(self):
        while not self._stopping.is_set():
            try:
                await _promote_due_jobs()
            except Exception:  # noqa: BLE001 - never let one bad tick kill the loop
                logger.exception("Scheduler tick failed")
            await asyncio.sleep(settings.SCHEDULER_POLL_INTERVAL_SECONDS)

    def start(self):
        self._stopping.clear()
        self._task = asyncio.create_task(self._loop())
        logger.info("Scheduler service started")

    async def stop(self, timeout: float = 5.0):
        self._stopping.set()
        if self._task:
            await asyncio.wait([self._task], timeout=timeout)
        logger.info("Scheduler service stopped")


scheduler_service = SchedulerService()
