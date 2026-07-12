"""
ORM models for the Distributed Job Scheduler.

Design notes (see docs/DESIGN_DECISIONS.md for full rationale):
- UUID primary keys everywhere: safe for distributed/multi-worker inserts,
  no auto-increment contention, and don't leak sequential IDs via the API.
- `Job` doubles as the "ScheduledJob" entity (cron_expression/next_run_at
  columns) instead of a separate table, since a scheduled job IS a job -
  splitting it out would just require constant joins/sync for no benefit.
- Retry policy is modeled as its own table (1:1 with Queue) purely because
  the assignment calls it out as a first-class concept; in practice it is
  a value object owned by the queue.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Boolean, ForeignKey, DateTime, Text,
    Enum, UniqueConstraint, Index, func, JSON
)
from sqlalchemy.dialects.postgresql import UUID, JSONB as PG_JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


def uuid_pk():
    return Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


# Postgres JSONB in production; falls back to portable JSON on SQLite so the
# unit test suite can run with zero external dependencies (see tests/conftest.py).
def JSONB():
    return PG_JSONB().with_variant(JSON(), "sqlite")


# --------------------------------------------------------------------------
# Enums
# --------------------------------------------------------------------------
class UserRole(str, enum.Enum):
    admin = "admin"
    member = "member"


class JobType(str, enum.Enum):
    immediate = "immediate"
    delayed = "delayed"
    scheduled = "scheduled"
    recurring = "recurring"
    batch = "batch"


class JobStatus(str, enum.Enum):
    queued = "queued"
    scheduled = "scheduled"
    claimed = "claimed"
    running = "running"
    completed = "completed"
    failed = "failed"
    dead_letter = "dead_letter"
    cancelled = "cancelled"


class RetryStrategy(str, enum.Enum):
    fixed = "fixed"
    linear = "linear"
    exponential = "exponential"


class WorkerStatus(str, enum.Enum):
    idle = "idle"
    busy = "busy"
    offline = "offline"


class LogLevel(str, enum.Enum):
    info = "info"
    warning = "warning"
    error = "error"


# --------------------------------------------------------------------------
# Core entities
# --------------------------------------------------------------------------
class Organization(Base):
    __tablename__ = "organizations"

    id = uuid_pk()
    name = Column(String(120), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="organization", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = uuid_pk()
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.member)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization", back_populates="users")


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("org_id", "name", name="uq_project_org_name"),)

    id = uuid_pk()
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization", back_populates="projects")
    queues = relationship("Queue", back_populates="project", cascade="all, delete-orphan")


class Queue(Base):
    __tablename__ = "queues"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_queue_project_name"),
        Index("ix_queue_project_priority", "project_id", "priority"),
    )

    id = uuid_pk()
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(120), nullable=False)
    priority = Column(Integer, nullable=False, default=0)  # higher = more important
    concurrency_limit = Column(Integer, nullable=False, default=1)
    is_paused = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project", back_populates="queues")
    retry_policy = relationship("RetryPolicy", back_populates="queue", uselist=False, cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="queue", cascade="all, delete-orphan")


class RetryPolicy(Base):
    __tablename__ = "retry_policies"

    id = uuid_pk()
    queue_id = Column(UUID(as_uuid=True), ForeignKey("queues.id", ondelete="CASCADE"), nullable=False, unique=True)
    strategy = Column(Enum(RetryStrategy), nullable=False, default=RetryStrategy.exponential)
    base_delay_seconds = Column(Integer, nullable=False, default=5)
    max_delay_seconds = Column(Integer, nullable=False, default=300)
    max_retries = Column(Integer, nullable=False, default=3)

    queue = relationship("Queue", back_populates="retry_policy")


class Job(Base):
    """
    A unit of work. Also represents "scheduled jobs": when job_type is
    `scheduled` or `recurring`, `next_run_at`/`cron_expression` drive the
    Scheduler service, which flips status -> queued when due.
    """
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_job_queue_status", "queue_id", "status"),
        Index("ix_job_status_run_at", "status", "run_at"),
        Index("ix_job_next_run_at", "next_run_at"),
        Index("ix_job_batch", "batch_id"),
    )

    id = uuid_pk()
    queue_id = Column(UUID(as_uuid=True), ForeignKey("queues.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    job_type = Column(Enum(JobType), nullable=False, default=JobType.immediate)
    payload = Column(JSONB(), nullable=False, default=dict)
    status = Column(Enum(JobStatus), nullable=False, default=JobStatus.queued, index=True)
    priority = Column(Integer, nullable=False, default=0)

    # Scheduling fields
    run_at = Column(DateTime(timezone=True), nullable=True)          # delayed / one-off scheduled
    cron_expression = Column(String(100), nullable=True)             # recurring
    next_run_at = Column(DateTime(timezone=True), nullable=True)     # recurring cursor

    # Batch grouping
    batch_id = Column(UUID(as_uuid=True), nullable=True)

    # Retry bookkeeping
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries_override = Column(Integer, nullable=True)

    # Execution / claim bookkeeping
    claimed_by = Column(UUID(as_uuid=True), ForeignKey("workers.id", ondelete="SET NULL"), nullable=True)
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    queue = relationship("Queue", back_populates="jobs")
    worker = relationship("Worker", back_populates="jobs")
    executions = relationship("JobExecution", back_populates="job", cascade="all, delete-orphan")
    logs = relationship("JobLog", back_populates="job", cascade="all, delete-orphan")
    dlq_entry = relationship("DeadLetterEntry", back_populates="job", uselist=False, cascade="all, delete-orphan")


class Worker(Base):
    __tablename__ = "workers"

    id = uuid_pk()
    name = Column(String(120), nullable=False, unique=True)
    status = Column(Enum(WorkerStatus), nullable=False, default=WorkerStatus.idle)
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    jobs = relationship("Job", back_populates="worker")
    heartbeats = relationship("WorkerHeartbeat", back_populates="worker", cascade="all, delete-orphan")


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"
    __table_args__ = (Index("ix_heartbeat_worker_time", "worker_id", "timestamp"),)

    id = uuid_pk()
    worker_id = Column(UUID(as_uuid=True), ForeignKey("workers.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    active_jobs = Column(Integer, nullable=False, default=0)

    worker = relationship("Worker", back_populates="heartbeats")


class JobExecution(Base):
    """One row per execution attempt. Gives us full retry history."""
    __tablename__ = "job_executions"
    __table_args__ = (Index("ix_execution_job", "job_id"),)

    id = uuid_pk()
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    worker_id = Column(UUID(as_uuid=True), ForeignKey("workers.id", ondelete="SET NULL"), nullable=True)
    attempt_number = Column(Integer, nullable=False, default=1)
    status = Column(Enum(JobStatus), nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    result = Column(JSONB(), nullable=True)
    error = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)

    job = relationship("Job", back_populates="executions")


class JobLog(Base):
    __tablename__ = "job_logs"
    __table_args__ = (Index("ix_log_job", "job_id"),)

    id = uuid_pk()
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    execution_id = Column(UUID(as_uuid=True), ForeignKey("job_executions.id", ondelete="CASCADE"), nullable=True)
    level = Column(Enum(LogLevel), nullable=False, default=LogLevel.info)
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    job = relationship("Job", back_populates="logs")


class DeadLetterEntry(Base):
    __tablename__ = "dead_letter_queue"

    id = uuid_pk()
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True)
    reason = Column(Text, nullable=False)
    retry_count_at_failure = Column(Integer, nullable=False)
    original_payload = Column(JSONB(), nullable=False)
    failed_at = Column(DateTime(timezone=True), server_default=func.now())

    job = relationship("Job", back_populates="dlq_entry")
