import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.models import User, Worker, Job, JobStatus
from app.schemas.schemas import WorkerOut

router = APIRouter(prefix="/api/workers", tags=["workers"])


@router.get("", response_model=list[WorkerOut])
def list_workers(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Worker).order_by(Worker.name).all()


@router.get("/{worker_id}", response_model=WorkerOut)
def get_worker(worker_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    worker = db.get(Worker, worker_id)
    if worker is None:
        raise HTTPException(404, "Worker not found")
    return worker


@router.get("/{worker_id}/current-job")
def worker_current_job(worker_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    job = (
        db.query(Job)
        .filter(Job.claimed_by == worker_id, Job.status.in_([JobStatus.claimed, JobStatus.running]))
        .first()
    )
    if job is None:
        return {"job": None}
    return {"job_id": job.id, "name": job.name, "status": job.status}
