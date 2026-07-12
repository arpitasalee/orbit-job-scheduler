"""
Integration test for atomic job claiming under real concurrency.

This is intentionally SKIPPED by default because it requires a live
Postgres connection (SQLite, used by the rest of the suite, does not
support `SELECT ... FOR UPDATE SKIP LOCKED` and would give a false sense
of safety). Run it explicitly against the docker-compose Postgres:

    docker compose up -d db
    export DATABASE_URL=postgresql://scheduler:scheduler@localhost:5432/scheduler_db
    RUN_INTEGRATION=1 pytest tests/test_concurrency_integration.py -v

It spins up several threads that all race to claim jobs from the same
queue concurrently and asserts that every job is claimed by exactly one
worker - i.e. no duplicate execution.
"""
import os
import threading
import uuid

import pytest

RUN_INTEGRATION = os.environ.get("RUN_INTEGRATION") == "1"


@pytest.mark.skipif(not RUN_INTEGRATION, reason="requires live Postgres; set RUN_INTEGRATION=1")
def test_no_double_claim_under_concurrent_workers():
    from app.core.database import SessionLocal
    from app.models.models import Organization, Project, Queue, RetryPolicy, Job, JobStatus
    from app.services.worker_pool import _claim_one_job

    db = SessionLocal()
    org = Organization(name=f"org-{uuid.uuid4().hex[:6]}")
    db.add(org)
    db.flush()
    project = Project(org_id=org.id, name="p")
    db.add(project)
    db.flush()
    queue = Queue(project_id=project.id, name="q", concurrency_limit=50)
    db.add(queue)
    db.flush()
    db.add(RetryPolicy(queue_id=queue.id))
    job_ids = []
    for i in range(20):
        job = Job(queue_id=queue.id, name=f"job-{i}", status=JobStatus.queued, payload={})
        db.add(job)
        db.flush()
        job_ids.append(job.id)
    db.commit()
    db.close()

    claimed_by: dict[uuid.UUID, uuid.UUID] = {}
    lock = threading.Lock()

    def worker_thread(worker_id):
        session = SessionLocal()
        for _ in range(25):
            job = _claim_one_job(session, worker_id)
            if job:
                with lock:
                    assert job.id not in claimed_by, "DUPLICATE CLAIM DETECTED"
                    claimed_by[job.id] = worker_id
        session.close()

    threads = [threading.Thread(target=worker_thread, args=(uuid.uuid4(),)) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(claimed_by) == len(job_ids), "Not all jobs were claimed exactly once"
