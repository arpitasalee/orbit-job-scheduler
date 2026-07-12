# Architecture Diagram

Orbit is a **monolithic** FastAPI application. The Worker Pool and Scheduler
are not separate deployables — they are asyncio background tasks started in
the same process via FastAPI's `lifespan`. This is a deliberate scope choice
for a 2-hour project (see `DESIGN_DECISIONS.md`): all the required
distributed-systems *concepts* (atomic claiming, concurrency limits,
heartbeats, graceful shutdown) are implemented for real, using
transaction-level Postgres locking — so the design scales to N real worker
containers with no code changes, just by running the worker loop in more
processes.

```mermaid
flowchart TB
    subgraph Client["Browser"]
        FE["React + Vite + Tailwind\nDashboard (polling every 3-5s)"]
    end

    subgraph API["FastAPI Monolith (single container)"]
        REST["REST API Layer\n(auth, projects, queues, jobs, workers, dashboard)"]
        AUTH["JWT Auth + Org-scoped\nAuthorization"]
        SCHED["Scheduler Service\n(asyncio loop)\npromotes due jobs\n(scheduled -> queued)"]
        POOL["Worker Pool\n(asyncio tasks x N)\natomic claim -> execute\n-> retry/DLQ -> heartbeat"]
    end

    subgraph DB["PostgreSQL"]
        TBLS[("organizations, users, projects,\nqueues, retry_policies, jobs,\njob_executions, job_logs,\nworkers, worker_heartbeats,\ndead_letter_queue")]
    end

    FE -- "HTTPS / JSON + JWT" --> REST
    REST --> AUTH
    REST <--> DB
    SCHED <--> DB
    POOL <--> DB
    SCHED -. "same process,\nshares connection pool" .-> POOL

    classDef box fill:#121A2B,stroke:#28375A,color:#E7ECF5;
    class Client,API,DB box;
```

### Request/Execution flow

```mermaid
sequenceDiagram
    participant U as User (Dashboard)
    participant API as FastAPI
    participant DB as Postgres
    participant SC as Scheduler loop
    participant W as Worker loop

    U->>API: POST /queues/{id}/jobs (create job)
    API->>DB: INSERT job (status=queued|scheduled)
    API-->>U: 201 Created

    loop every SCHEDULER_POLL_INTERVAL
        SC->>DB: SELECT jobs WHERE status=scheduled AND run_at<=now
        SC->>DB: UPDATE status=queued
    end

    loop every WORKER_POLL_INTERVAL (per worker)
        W->>DB: SELECT ... FOR UPDATE SKIP LOCKED (claim 1 job)
        DB-->>W: job row (locked, only this worker sees it)
        W->>DB: UPDATE status=claimed, claimed_by=worker_id
        W->>W: execute payload (async)
        alt success
            W->>DB: UPDATE status=completed, INSERT execution row
        else failure, retries remain
            W->>DB: UPDATE status=scheduled, run_at=now+backoff
        else failure, retries exhausted
            W->>DB: UPDATE status=dead_letter, INSERT dead_letter_queue row
        end
        W->>DB: UPDATE worker heartbeat
    end

    U->>API: GET /dashboard/health (polling)
    API->>DB: aggregate counts
    API-->>U: JSON metrics
```
