# Entity-Relationship Diagram

```mermaid
erDiagram
    ORGANIZATIONS ||--o{ USERS : "has"
    ORGANIZATIONS ||--o{ PROJECTS : "owns"
    PROJECTS ||--o{ QUEUES : "owns"
    QUEUES ||--|| RETRY_POLICIES : "configured by"
    QUEUES ||--o{ JOBS : "contains"
    JOBS ||--o{ JOB_EXECUTIONS : "has attempts"
    JOBS ||--o{ JOB_LOGS : "has logs"
    JOBS ||--o| DEAD_LETTER_QUEUE : "terminally failed into"
    WORKERS ||--o{ JOBS : "claims"
    WORKERS ||--o{ JOB_EXECUTIONS : "executes"
    WORKERS ||--o{ WORKER_HEARTBEATS : "reports"

    ORGANIZATIONS {
        uuid id PK
        string name UK
        timestamp created_at
    }
    USERS {
        uuid id PK
        uuid org_id FK
        string email UK
        string password_hash
        enum role
        timestamp created_at
    }
    PROJECTS {
        uuid id PK
        uuid org_id FK
        string name
        text description
        timestamp created_at
    }
    QUEUES {
        uuid id PK
        uuid project_id FK
        string name
        int priority
        int concurrency_limit
        bool is_paused
        timestamp created_at
    }
    RETRY_POLICIES {
        uuid id PK
        uuid queue_id FK "unique (1:1)"
        enum strategy "fixed|linear|exponential"
        int base_delay_seconds
        int max_delay_seconds
        int max_retries
    }
    JOBS {
        uuid id PK
        uuid queue_id FK
        string name
        enum job_type "immediate|delayed|scheduled|recurring|batch"
        jsonb payload
        enum status "queued|scheduled|claimed|running|completed|failed|dead_letter|cancelled"
        int priority
        timestamp run_at "delayed/scheduled/backoff"
        string cron_expression "recurring"
        timestamp next_run_at "recurring cursor"
        uuid batch_id "groups batch jobs"
        int retry_count
        int max_retries_override
        uuid claimed_by FK
        timestamp claimed_at
        timestamp started_at
        timestamp completed_at
        timestamp created_at
        timestamp updated_at
    }
    JOB_EXECUTIONS {
        uuid id PK
        uuid job_id FK
        uuid worker_id FK
        int attempt_number
        enum status
        timestamp started_at
        timestamp completed_at
        jsonb result
        text error
        int duration_ms
    }
    JOB_LOGS {
        uuid id PK
        uuid job_id FK
        uuid execution_id FK
        enum level "info|warning|error"
        text message
        timestamp timestamp
    }
    WORKERS {
        uuid id PK
        string name UK
        enum status "idle|busy|offline"
        timestamp last_heartbeat_at
        timestamp created_at
    }
    WORKER_HEARTBEATS {
        uuid id PK
        uuid worker_id FK
        timestamp timestamp
        int active_jobs
    }
    DEAD_LETTER_QUEUE {
        uuid id PK
        uuid job_id FK "unique (1:1)"
        text reason
        int retry_count_at_failure
        jsonb original_payload
        timestamp failed_at
    }
```

## Notes on normalization, keys, and cascading

- **Primary keys**: every table uses a UUID PK (`uuid4`, client/app-generated).
  This avoids sequential-ID contention across concurrent inserts from
  multiple workers and doesn't leak row counts through the API.
- **Foreign keys & cascade behavior**:
  - `organizations -> users/projects`: `ON DELETE CASCADE` — deleting a tenant
    cleans up everything it owns.
  - `projects -> queues`, `queues -> jobs`, `jobs -> job_executions/job_logs`,
    `jobs -> dead_letter_queue`: all `CASCADE` — child records are meaningless
    without their parent and we don't want orphaned rows.
  - `workers -> jobs.claimed_by` and `workers -> job_executions.worker_id`:
    `ON DELETE SET NULL` — a worker can be decommissioned without destroying
    the historical record of what it executed.
- **Normalization**: schema is in 3NF. `RetryPolicy` is split out as its own
  table (1:1 with `Queue`) purely to give it first-class identity per the
  assignment; `Job` intentionally denormalizes a `priority` copy from its
  queue at creation time so per-job overrides are possible without a queue
  join on every claim query.
- **"Scheduled Jobs" as an entity**: rather than a separate `scheduled_jobs`
  table, `Job` carries `cron_expression`/`run_at`/`next_run_at` directly. A
  scheduled job *is* a job with different metadata — splitting it out would
  require constant syncing between two tables for a job that ultimately runs
  through the exact same claim/execute/retry pipeline.
- **Key indexes** (all justified by an actual query in the code):
  - `jobs(queue_id, status)` — per-queue stats and job explorer filtering.
  - `jobs(status, run_at)` — the scheduler's "which scheduled jobs are due"
    sweep.
  - `jobs(next_run_at)` — future use for cron look-ahead / UI.
  - `jobs(batch_id)` — batch progress lookups.
  - `queues(project_id, priority)` — listing queues ordered by priority.
  - `job_executions(job_id)`, `job_logs(job_id)` — execution/log history per
    job (the job detail page's primary query).
  - `worker_heartbeats(worker_id, timestamp)` — staleness checks / time
    series.
  - unique constraints on `(org_id, project.name)`, `(project_id, queue.name)`,
    `users.email`, `workers.name`, `retry_policies.queue_id`,
    `dead_letter_queue.job_id` prevent duplicate/ambiguous rows.
