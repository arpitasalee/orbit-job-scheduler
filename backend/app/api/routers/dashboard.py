from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.models import User, Job, JobStatus, Worker, WorkerStatus, DeadLetterEntry, Queue, Project
from app.schemas.schemas import SystemHealth

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/health", response_model=SystemHealth)
def system_health(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    org_job_ids = (
        db.query(Job.id)
        .join(Queue, Queue.id == Job.queue_id)
        .join(Project, Project.id == Queue.project_id)
        .filter(Project.org_id == current_user.org_id)
    )
    base_q = db.query(Job).filter(Job.id.in_(org_job_ids))

    def count(*statuses):
        return base_q.filter(Job.status.in_(statuses)).count()

    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    throughput = base_q.filter(Job.status == JobStatus.completed, Job.completed_at >= one_hour_ago).count()

    total_workers = db.query(Worker).count()
    active_workers = db.query(Worker).filter(Worker.status != WorkerStatus.offline).count()

    return SystemHealth(
        total_jobs=base_q.count(),
        queued=count(JobStatus.queued, JobStatus.scheduled, JobStatus.claimed),
        running=count(JobStatus.running),
        completed=count(JobStatus.completed),
        failed=count(JobStatus.failed),
        dead_letter=count(JobStatus.dead_letter),
        active_workers=active_workers,
        total_workers=total_workers,
        throughput_last_hour=throughput,
    )


@router.get("/dead-letter")
def dead_letter_entries(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    entries = (
        db.query(DeadLetterEntry)
        .join(Job, Job.id == DeadLetterEntry.job_id)
        .join(Queue, Queue.id == Job.queue_id)
        .join(Project, Project.id == Queue.project_id)
        .filter(Project.org_id == current_user.org_id)
        .order_by(DeadLetterEntry.failed_at.desc())
        .all()
    )
    return [
        {
            "id": e.id,
            "job_id": e.job_id,
            "job_name": e.job.name,
            "reason": e.reason,
            "retry_count_at_failure": e.retry_count_at_failure,
            "failed_at": e.failed_at,
        }
        for e in entries
    ]


@router.get("/throughput-series")
def throughput_series(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Completed-job counts bucketed per minute for the last 30 minutes (simple sparkline data)."""
    since = datetime.now(timezone.utc) - timedelta(minutes=30)
    org_job_ids = (
        db.query(Job.id)
        .join(Queue, Queue.id == Job.queue_id)
        .join(Project, Project.id == Queue.project_id)
        .filter(Project.org_id == current_user.org_id)
    )
    rows = (
        db.query(func.date_trunc("minute", Job.completed_at).label("bucket"), func.count(Job.id))
        .filter(Job.id.in_(org_job_ids), Job.status == JobStatus.completed, Job.completed_at >= since)
        .group_by("bucket")
        .order_by("bucket")
        .all()
    )
    return [{"bucket": b.isoformat(), "count": c} for b, c in rows]
