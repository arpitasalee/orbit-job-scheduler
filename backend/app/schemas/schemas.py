import uuid
from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, EmailStr, Field

from app.models.models import JobType, JobStatus, RetryStrategy, WorkerStatus, UserRole


# ---------------- Auth ----------------
class RegisterRequest(BaseModel):
    org_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    role: UserRole
    org_id: uuid.UUID

    class Config:
        from_attributes = True


# ---------------- Project ----------------
class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: Optional[str] = None


class ProjectOut(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------- Retry Policy ----------------
class RetryPolicyIn(BaseModel):
    strategy: RetryStrategy = RetryStrategy.exponential
    base_delay_seconds: int = Field(default=5, ge=1)
    max_delay_seconds: int = Field(default=300, ge=1)
    max_retries: int = Field(default=3, ge=0, le=20)


class RetryPolicyOut(RetryPolicyIn):
    id: uuid.UUID

    class Config:
        from_attributes = True


# ---------------- Queue ----------------
class QueueCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    priority: int = 0
    concurrency_limit: int = Field(default=1, ge=1, le=100)
    retry_policy: Optional[RetryPolicyIn] = None


class QueueUpdate(BaseModel):
    priority: Optional[int] = None
    concurrency_limit: Optional[int] = Field(default=None, ge=1, le=100)
    is_paused: Optional[bool] = None
    retry_policy: Optional[RetryPolicyIn] = None


class QueueOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    priority: int
    concurrency_limit: int
    is_paused: bool
    created_at: datetime
    retry_policy: Optional[RetryPolicyOut] = None

    class Config:
        from_attributes = True


class QueueStats(BaseModel):
    queue_id: uuid.UUID
    queued: int
    running: int
    completed: int
    failed: int
    dead_letter: int


# ---------------- Job ----------------
class JobCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    job_type: JobType = JobType.immediate
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: Optional[int] = None
    run_at: Optional[datetime] = None            # required for delayed/scheduled
    cron_expression: Optional[str] = None         # required for recurring
    max_retries_override: Optional[int] = None
    batch_id: Optional[uuid.UUID] = None


class BatchJobCreate(BaseModel):
    name_prefix: str = Field(min_length=1, max_length=150)
    payloads: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    priority: Optional[int] = None


class JobOut(BaseModel):
    id: uuid.UUID
    queue_id: uuid.UUID
    name: str
    job_type: JobType
    payload: dict[str, Any]
    status: JobStatus
    priority: int
    run_at: Optional[datetime]
    cron_expression: Optional[str]
    next_run_at: Optional[datetime]
    batch_id: Optional[uuid.UUID]
    retry_count: int
    claimed_by: Optional[uuid.UUID]
    claimed_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class JobLogOut(BaseModel):
    id: uuid.UUID
    level: str
    message: str
    timestamp: datetime

    class Config:
        from_attributes = True


class JobExecutionOut(BaseModel):
    id: uuid.UUID
    worker_id: Optional[uuid.UUID]
    attempt_number: int
    status: JobStatus
    started_at: datetime
    completed_at: Optional[datetime]
    result: Optional[dict[str, Any]]
    error: Optional[str]
    duration_ms: Optional[int]

    class Config:
        from_attributes = True


class JobDetailOut(JobOut):
    executions: list[JobExecutionOut] = []
    logs: list[JobLogOut] = []


# ---------------- Worker ----------------
class WorkerOut(BaseModel):
    id: uuid.UUID
    name: str
    status: WorkerStatus
    last_heartbeat_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------- Dashboard ----------------
class SystemHealth(BaseModel):
    total_jobs: int
    queued: int
    running: int
    completed: int
    failed: int
    dead_letter: int
    active_workers: int
    total_workers: int
    throughput_last_hour: int


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int
