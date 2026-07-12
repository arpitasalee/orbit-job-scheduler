import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user, get_project_or_404, get_queue_or_404
from app.models.models import User, Queue, RetryPolicy, Job, JobStatus
from app.schemas.schemas import QueueCreate, QueueUpdate, QueueOut, QueueStats

router = APIRouter(prefix="/api", tags=["queues"])


@router.post("/projects/{project_id}/queues", response_model=QueueOut, status_code=201)
def create_queue(project_id: uuid.UUID, payload: QueueCreate, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    get_project_or_404(project_id, db, current_user)
    if db.query(Queue).filter(Queue.project_id == project_id, Queue.name == payload.name).first():
        raise HTTPException(status_code=400, detail="A queue with this name already exists in the project")

    queue = Queue(
        project_id=project_id, name=payload.name, priority=payload.priority,
        concurrency_limit=payload.concurrency_limit,
    )
    db.add(queue)
    db.flush()

    rp = payload.retry_policy
    retry_policy = RetryPolicy(
        queue_id=queue.id,
        strategy=(rp.strategy if rp else "exponential"),
        base_delay_seconds=(rp.base_delay_seconds if rp else 5),
        max_delay_seconds=(rp.max_delay_seconds if rp else 300),
        max_retries=(rp.max_retries if rp else 3),
    )
    db.add(retry_policy)
    db.commit()
    db.refresh(queue)
    return queue


@router.get("/projects/{project_id}/queues", response_model=list[QueueOut])
def list_queues(project_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    get_project_or_404(project_id, db, current_user)
    return db.query(Queue).filter(Queue.project_id == project_id).order_by(Queue.priority.desc()).all()


@router.get("/queues/{queue_id}", response_model=QueueOut)
def get_queue(queue_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return get_queue_or_404(queue_id, db, current_user)


@router.patch("/queues/{queue_id}", response_model=QueueOut)
def update_queue(queue_id: uuid.UUID, payload: QueueUpdate, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    queue = get_queue_or_404(queue_id, db, current_user)
    if payload.priority is not None:
        queue.priority = payload.priority
    if payload.concurrency_limit is not None:
        queue.concurrency_limit = payload.concurrency_limit
    if payload.is_paused is not None:
        queue.is_paused = payload.is_paused
    if payload.retry_policy is not None:
        rp = queue.retry_policy
        rp.strategy = payload.retry_policy.strategy
        rp.base_delay_seconds = payload.retry_policy.base_delay_seconds
        rp.max_delay_seconds = payload.retry_policy.max_delay_seconds
        rp.max_retries = payload.retry_policy.max_retries
    db.commit()
    db.refresh(queue)
    return queue


@router.post("/queues/{queue_id}/pause", response_model=QueueOut)
def pause_queue(queue_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    queue = get_queue_or_404(queue_id, db, current_user)
    queue.is_paused = True
    db.commit()
    db.refresh(queue)
    return queue


@router.post("/queues/{queue_id}/resume", response_model=QueueOut)
def resume_queue(queue_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    queue = get_queue_or_404(queue_id, db, current_user)
    queue.is_paused = False
    db.commit()
    db.refresh(queue)
    return queue


@router.get("/queues/{queue_id}/stats", response_model=QueueStats)
def queue_stats(queue_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    get_queue_or_404(queue_id, db, current_user)
    rows = (
        db.query(Job.status, func.count(Job.id))
        .filter(Job.queue_id == queue_id)
        .group_by(Job.status)
        .all()
    )
    counts = {status: 0 for status in ["queued", "running", "completed", "failed", "dead_letter"]}
    for status_val, count in rows:
        key = status_val.value if hasattr(status_val, "value") else status_val
        if key in counts:
            counts[key] = count
        elif key in ("scheduled", "claimed"):
            counts["queued"] += count
    return QueueStats(queue_id=queue_id, **counts)


@router.delete("/queues/{queue_id}", status_code=204)
def delete_queue(queue_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    queue = get_queue_or_404(queue_id, db, current_user)
    db.delete(queue)
    db.commit()
