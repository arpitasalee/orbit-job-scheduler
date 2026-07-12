import uuid
from datetime import datetime, timezone
from typing import Optional

from croniter import croniter
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.api.deps import get_current_user, get_queue_or_404
from app.models.models import User, Job, JobStatus, JobType, DeadLetterEntry
from app.schemas.schemas import JobCreate, BatchJobCreate, JobOut, JobDetailOut, PaginatedResponse

router = APIRouter(prefix="/api", tags=["jobs"])


def _validate_and_build_job(queue_id, payload: JobCreate) -> Job:
    status_ = JobStatus.queued
    run_at = payload.run_at
    next_run_at = None

    if payload.job_type == JobType.delayed:
        if not payload.run_at:
            raise HTTPException(400, "run_at is required for delayed jobs")
        status_ = JobStatus.scheduled
    elif payload.job_type == JobType.scheduled:
        if not payload.run_at:
            raise HTTPException(400, "run_at is required for scheduled jobs")
        status_ = JobStatus.scheduled
    elif payload.job_type == JobType.recurring:
        if not payload.cron_expression or not croniter.is_valid(payload.cron_expression):
            raise HTTPException(400, "A valid cron_expression is required for recurring jobs")
        status_ = JobStatus.scheduled
        next_run_at = croniter(payload.cron_expression, datetime.now(timezone.utc)).get_next(datetime)

    return Job(
        queue_id=queue_id,
        name=payload.name,
        job_type=payload.job_type,
        payload=payload.payload,
        status=status_,
        priority=payload.priority or 0,
        run_at=run_at,
        cron_expression=payload.cron_expression,
        next_run_at=next_run_at,
        max_retries_override=payload.max_retries_override,
        batch_id=payload.batch_id,
    )


@router.post("/queues/{queue_id}/jobs", response_model=JobOut, status_code=201)
def create_job(queue_id: uuid.UUID, payload: JobCreate, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    get_queue_or_404(queue_id, db, current_user)
    job = _validate_and_build_job(queue_id, payload)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.post("/queues/{queue_id}/jobs/batch", response_model=list[JobOut], status_code=201)
def create_batch_jobs(queue_id: uuid.UUID, payload: BatchJobCreate, db: Session = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    """Creates N jobs sharing one batch_id so progress can be tracked together."""
    get_queue_or_404(queue_id, db, current_user)
    batch_id = uuid.uuid4()
    jobs = []
    for i, item_payload in enumerate(payload.payloads):
        job = Job(
            queue_id=queue_id,
            name=f"{payload.name_prefix}-{i + 1}",
            job_type=JobType.batch,
            payload=item_payload,
            status=JobStatus.queued,
            priority=payload.priority or 0,
            batch_id=batch_id,
        )
        db.add(job)
        jobs.append(job)
    db.commit()
    for job in jobs:
        db.refresh(job)
    return jobs


@router.get("/queues/{queue_id}/jobs", response_model=PaginatedResponse)
def list_jobs(
    queue_id: uuid.UUID,
    status_filter: Optional[JobStatus] = Query(default=None, alias="status"),
    job_type: Optional[JobType] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_queue_or_404(queue_id, db, current_user)
    q = db.query(Job).filter(Job.queue_id == queue_id)
    if status_filter:
        q = q.filter(Job.status == status_filter)
    if job_type:
        q = q.filter(Job.job_type == job_type)
    total = q.count()
    items = (
        q.order_by(Job.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedResponse(items=[JobOut.model_validate(j) for j in items], total=total, page=page, page_size=page_size)


@router.get("/jobs/{job_id}", response_model=JobDetailOut)
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    job = (
        db.query(Job)
        .options(joinedload(Job.executions), joinedload(Job.logs))
        .filter(Job.id == job_id)
        .first()
    )
    if job is None:
        raise HTTPException(404, "Job not found")
    get_queue_or_404(job.queue_id, db, current_user)  # ownership check
    return job


@router.post("/jobs/{job_id}/retry", response_model=JobOut)
def retry_job(job_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Manually re-queue a job stuck in `failed` or `dead_letter` (e.g. from the dashboard)."""
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    get_queue_or_404(job.queue_id, db, current_user)
    if job.status not in (JobStatus.failed, JobStatus.dead_letter):
        raise HTTPException(400, "Only failed or dead-lettered jobs can be manually retried")

    job.status = JobStatus.queued
    job.retry_count = 0
    job.claimed_by = None
    job.claimed_at = None
    job.started_at = None
    job.completed_at = None

    dlq_entry = db.query(DeadLetterEntry).filter(DeadLetterEntry.job_id == job_id).first()
    if dlq_entry:
        db.delete(dlq_entry)

    db.commit()
    db.refresh(job)
    return job


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
def cancel_job(job_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    get_queue_or_404(job.queue_id, db, current_user)
    if job.status in (JobStatus.completed, JobStatus.running):
        raise HTTPException(400, f"Cannot cancel a job in '{job.status.value}' state")
    job.status = JobStatus.cancelled
    db.commit()
    db.refresh(job)
    return job
