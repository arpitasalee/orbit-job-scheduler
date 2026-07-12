"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

job_type_enum = pg.ENUM("immediate", "delayed", "scheduled", "recurring", "batch", name="jobtype")
job_status_enum = pg.ENUM("queued", "scheduled", "claimed", "running", "completed", "failed",
                           "dead_letter", "cancelled", name="jobstatus")
retry_strategy_enum = pg.ENUM("fixed", "linear", "exponential", name="retrystrategy")
worker_status_enum = pg.ENUM("idle", "busy", "offline", name="workerstatus")
user_role_enum = pg.ENUM("admin", "member", name="userrole")
log_level_enum = pg.ENUM("info", "warning", "error", name="loglevel")


def upgrade() -> None:
    bind = op.get_bind()
    for enum in (job_type_enum, job_status_enum, retry_strategy_enum, worker_status_enum, user_role_enum, log_level_enum):
        enum.create(bind, checkfirst=True)

    op.create_table(
        "organizations",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "users",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", user_role_enum, nullable=False, server_default="member"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "projects",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", pg.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("org_id", "name", name="uq_project_org_name"),
    )

    op.create_table(
        "queues",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", pg.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("concurrency_limit", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_paused", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "name", name="uq_queue_project_name"),
    )
    op.create_index("ix_queue_project_priority", "queues", ["project_id", "priority"])

    op.create_table(
        "retry_policies",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("queue_id", pg.UUID(as_uuid=True), sa.ForeignKey("queues.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("strategy", retry_strategy_enum, nullable=False, server_default="exponential"),
        sa.Column("base_delay_seconds", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("max_delay_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
    )

    op.create_table(
        "workers",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("status", worker_status_enum, nullable=False, server_default="idle"),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "jobs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("queue_id", pg.UUID(as_uuid=True), sa.ForeignKey("queues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("job_type", job_type_enum, nullable=False, server_default="immediate"),
        sa.Column("payload", pg.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", job_status_enum, nullable=False, server_default="queued"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cron_expression", sa.String(100), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("batch_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries_override", sa.Integer(), nullable=True),
        sa.Column("claimed_by", pg.UUID(as_uuid=True), sa.ForeignKey("workers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_job_queue_status", "jobs", ["queue_id", "status"])
    op.create_index("ix_job_status_run_at", "jobs", ["status", "run_at"])
    op.create_index("ix_job_next_run_at", "jobs", ["next_run_at"])
    op.create_index("ix_job_batch", "jobs", ["batch_id"])
    op.create_index("ix_jobs_status", "jobs", ["status"])

    op.create_table(
        "job_executions",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", pg.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("worker_id", pg.UUID(as_uuid=True), sa.ForeignKey("workers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", job_status_enum, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", pg.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
    )
    op.create_index("ix_execution_job", "job_executions", ["job_id"])

    op.create_table(
        "worker_heartbeats",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("worker_id", pg.UUID(as_uuid=True), sa.ForeignKey("workers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("active_jobs", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_heartbeat_worker_time", "worker_heartbeats", ["worker_id", "timestamp"])

    op.create_table(
        "job_logs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", pg.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("execution_id", pg.UUID(as_uuid=True), sa.ForeignKey("job_executions.id", ondelete="CASCADE"), nullable=True),
        sa.Column("level", log_level_enum, nullable=False, server_default="info"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_log_job", "job_logs", ["job_id"])

    op.create_table(
        "dead_letter_queue",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", pg.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("retry_count_at_failure", sa.Integer(), nullable=False),
        sa.Column("original_payload", pg.JSONB(), nullable=False),
        sa.Column("failed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("dead_letter_queue")
    op.drop_table("job_logs")
    op.drop_table("worker_heartbeats")
    op.drop_table("job_executions")
    op.drop_table("jobs")
    op.drop_table("workers")
    op.drop_table("retry_policies")
    op.drop_table("queues")
    op.drop_table("projects")
    op.drop_table("users")
    op.drop_table("organizations")

    bind = op.get_bind()
    for enum in (job_type_enum, job_status_enum, retry_strategy_enum, worker_status_enum, user_role_enum, log_level_enum):
        enum.drop(bind, checkfirst=True)
