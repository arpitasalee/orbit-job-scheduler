"""
In-process worker pool.

The assignment asks for "a worker service that polls queues, atomically
claims jobs, executes them concurrently, sends heartbeats, and supports
graceful shutdown". Running each worker as its own asyncio task inside the
same process (rather than a separate container) is a deliberate scope
decision for a 2-hour project: it demonstrates every required concurrency
concept (atomic claiming, concurrency limits, heartbeats, graceful drain)
without the operational overhead of a second deployable service. The claim
query is fully SQL-transaction based (SELECT ... FOR UPDATE SKIP LOCKED),
so the design generalizes directly to N real worker processes/containers -
you would simply run `python -m app.worker_main` in more containers.
"""
import asyncio
import logging
import random
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.models import (
    Job, JobStatus, Queue, Worker, WorkerStatus, WorkerHeartbeat,
    JobExecution, JobLog, LogLevel, DeadLetterEntry, RetryPolicy,
)
from app.services.retry import compute_retry_delay_seconds

logger = logging.getLogger("worker_pool")


def _claim_one_job(db: Session, worker_id: uuid.UUID) -> Job | None:
    """
    Atomically claims the single highest-priority eligible job across all
    non-paused queues, respecting each queue's concurrency_limit.

    `SELECT ... FOR UPDATE SKIP LOCKED` is the crux of "atomic claiming":
    if two workers race for the same row, the loser simply skips it and
    looks at the next candidate instead of blocking or double-claiming.
    """
    now = datetime.now(timezone.utc)

    candidates = (
        db.query(Job)
        .join(Queue, Queue.id == Job.queue_id)
        .filter(Queue.is_paused.is_(False))
        .filter(Job.status == JobStatus.queued)
        .order_by(Job.priority.desc(), Job.created_at.asc())
        .with_for_update(skip_locked=True, of=Job)
        .limit(25)  # small candidate window keeps the lock scope cheap
        .all()
    )

    for job in candidates:
        queue = job.queue
        running_count = (
            db.query(Job)
            .filter(Job.queue_id == queue.id, Job.status.in_([JobStatus.claimed, JobStatus.running]))
            .count()
        )
        if running_count >= queue.concurrency_limit:
            continue  # this queue is at capacity, try the next candidate

        job.status = JobStatus.claimed
        job.claimed_by = worker_id
        job.claimed_at = now
        db.add(job)
        db.commit()
        return job

    db.rollback()
    return None


async def _run_job_payload(payload: dict) -> dict:
    """
    Simulated job execution. In a real system this would dispatch to a
    task-type registry (send_email, generate_report, etc). For the demo we
    honor two payload conventions so failures/DLQ are easy to exercise:
      - {"duration_ms": 500}         -> sleeps to simulate work
      - {"fail": true}               -> always raises
      - {"fail_until_attempt": 3}    -> fails until that attempt number
    """
    duration_ms = payload.get("duration_ms", random.randint(200, 800))
    await asyncio.sleep(duration_ms / 1000)

    if payload.get("fail") is True:
        raise RuntimeError("Simulated permanent failure")

    fail_until = payload.get("fail_until_attempt")
    if fail_until and payload.get("_attempt", 1) < fail_until:
        raise RuntimeError(f"Simulated transient failure before attempt {fail_until}")

    return {"ok": True, "duration_ms": duration_ms}


async def _execute_job(worker_id: uuid.UUID, job_id: uuid.UUID):
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job is None:
            return
        job.status = JobStatus.running
        job.started_at = datetime.now(timezone.utc)
        attempt_number = job.retry_count + 1
        execution = JobExecution(job_id=job.id, worker_id=worker_id, attempt_number=attempt_number,
                                  status=JobStatus.running)
        db.add(execution)
        db.add(JobLog(job_id=job.id, level=LogLevel.info,
                       message=f"Attempt {attempt_number} started on worker {worker_id}"))
        db.commit()

        payload = dict(job.payload or {})
        payload["_attempt"] = attempt_number
        start = time.monotonic()
        try:
            result = await _run_job_payload(payload)
            duration_ms = int((time.monotonic() - start) * 1000)

            job.status = JobStatus.completed
            job.completed_at = datetime.now(timezone.utc)
            execution.status = JobStatus.completed
            execution.completed_at = job.completed_at
            execution.result = result
            execution.duration_ms = duration_ms
            db.add(JobLog(job_id=job.id, level=LogLevel.info, message="Completed successfully"))

            # Reschedule recurring jobs for their next cron tick.
            if job.job_type.value == "recurring" and job.cron_expression:
                from croniter import croniter
                next_run = croniter(job.cron_expression, datetime.now(timezone.utc)).get_next(datetime)
                sibling = Job(
                    queue_id=job.queue_id, name=job.name, job_type=job.job_type,
                    payload=job.payload, status=JobStatus.scheduled, priority=job.priority,
                    cron_expression=job.cron_expression, next_run_at=next_run,
                )
                db.add(sibling)

            db.commit()
        except Exception as exc:  # noqa: BLE001 - job payload errors are expected/user-driven
            duration_ms = int((time.monotonic() - start) * 1000)
            execution.status = JobStatus.failed
            execution.completed_at = datetime.now(timezone.utc)
            execution.error = str(exc)
            execution.duration_ms = duration_ms
            db.add(JobLog(job_id=job.id, level=LogLevel.error, message=f"Attempt {attempt_number} failed: {exc}"))

            retry_policy = job.queue.retry_policy
            max_retries = job.max_retries_override if job.max_retries_override is not None else retry_policy.max_retries

            if job.retry_count < max_retries:
                job.retry_count += 1
                job.status = JobStatus.queued  # scheduler/next poll will pick it up once due
                job.claimed_by = None
                job.claimed_at = None
                delay = compute_retry_delay_seconds(
                    retry_policy.strategy, retry_policy.base_delay_seconds,
                    retry_policy.max_delay_seconds, job.retry_count,
                )
                job.run_at = datetime.now(timezone.utc)
                job.status = JobStatus.scheduled
                from datetime import timedelta
                job.run_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
                db.add(JobLog(job_id=job.id, level=LogLevel.warning,
                               message=f"Retry {job.retry_count}/{max_retries} scheduled in {delay}s"))
            else:
                job.status = JobStatus.dead_letter
                db.add(DeadLetterEntry(
                    job_id=job.id, reason=str(exc), retry_count_at_failure=job.retry_count,
                    original_payload=job.payload,
                ))
                db.add(JobLog(job_id=job.id, level=LogLevel.error, message="Moved to Dead Letter Queue"))
            db.commit()
    finally:
        db.close()


class WorkerPool:
    """Owns N worker identities and their asyncio poll loops."""

    def __init__(self, pool_size: int = settings.WORKER_POOL_SIZE):
        self.pool_size = pool_size
        self._stopping = asyncio.Event()
        self._tasks: list[asyncio.Task] = []
        self.worker_ids: list[uuid.UUID] = []

    def _register_workers(self):
        db = SessionLocal()
        try:
            self.worker_ids = []
            for i in range(self.pool_size):
                name = f"worker-{i + 1}"
                worker = db.query(Worker).filter(Worker.name == name).first()
                if worker is None:
                    worker = Worker(name=name, status=WorkerStatus.idle)
                    db.add(worker)
                    db.commit()
                    db.refresh(worker)
                else:
                    worker.status = WorkerStatus.idle
                    db.commit()
                self.worker_ids.append(worker.id)
        finally:
            db.close()

    async def _worker_loop(self, worker_id: uuid.UUID):
        last_heartbeat = 0.0
        while not self._stopping.is_set():
            db = SessionLocal()
            try:
                job = _claim_one_job(db, worker_id)
            finally:
                db.close()

            if job:
                db2 = SessionLocal()
                try:
                    w = db2.get(Worker, worker_id)
                    w.status = WorkerStatus.busy
                    db2.commit()
                finally:
                    db2.close()
                await _execute_job(worker_id, job.id)
                db3 = SessionLocal()
                try:
                    w = db3.get(Worker, worker_id)
                    w.status = WorkerStatus.idle
                    db3.commit()
                finally:
                    db3.close()
            else:
                await asyncio.sleep(settings.WORKER_POLL_INTERVAL_SECONDS)

            now = time.monotonic()
            if now - last_heartbeat >= settings.WORKER_HEARTBEAT_INTERVAL_SECONDS:
                self._send_heartbeat(worker_id)
                last_heartbeat = now

        # graceful shutdown: mark offline once the current job (if any) finished
        db = SessionLocal()
        try:
            w = db.get(Worker, worker_id)
            w.status = WorkerStatus.offline
            db.commit()
        finally:
            db.close()

    @staticmethod
    def _send_heartbeat(worker_id: uuid.UUID):
        db = SessionLocal()
        try:
            w = db.get(Worker, worker_id)
            w.last_heartbeat_at = datetime.now(timezone.utc)
            active = 1 if w.status == WorkerStatus.busy else 0
            db.add(WorkerHeartbeat(worker_id=worker_id, active_jobs=active))
            db.commit()
        finally:
            db.close()

    async def start(self):
        self._register_workers()
        self._stopping.clear()
        self._tasks = [asyncio.create_task(self._worker_loop(wid)) for wid in self.worker_ids]
        logger.info("Worker pool started with %d workers", self.pool_size)

    async def stop(self, timeout: float = 15.0):
        """Signals all loops to stop after finishing their current job (graceful shutdown)."""
        self._stopping.set()
        if self._tasks:
            await asyncio.wait(self._tasks, timeout=timeout)
        logger.info("Worker pool stopped gracefully")


worker_pool = WorkerPool()
