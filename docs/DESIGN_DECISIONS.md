# Design Decisions & Trade-offs

This document explains the major architectural choices and what was
deliberately left out, given a scoped, time-boxed internship deliverable.

## 1. Monolith with in-process worker pool, not separate services

**Decision**: The Worker Pool and Scheduler run as asyncio background tasks
inside the same FastAPI process, rather than as independently deployed
services/containers.

**Why**: The assignment explicitly calls for a monolithic architecture. A
"real" distributed deployment would run `N` worker containers polling the
same database. The important engineering property to demonstrate is **atomic
job claiming under concurrency** — and that property lives entirely in the
SQL (`SELECT ... FOR UPDATE SKIP LOCKED`), not in how many OS processes are
running it. Because the claim logic is a self-contained function
(`_claim_one_job`) operating over a normal DB session, this design scales
horizontally with zero code changes: point more worker processes at the same
Postgres instance and they will safely race for jobs via row-level locking.

**Trade-off**: A single process restart takes down both API and workers
together. In production you'd split these into separate deployables with
independent scaling and failure domains.

## 2. Atomic claiming via `SELECT ... FOR UPDATE SKIP LOCKED`

**Decision**: Workers claim jobs with a row-locking query that skips rows
already locked by another transaction, rather than optimistic locking
(compare-and-swap on a version column) or an external lock service (Redis,
etc).

**Why**: `FOR UPDATE SKIP LOCKED` is Postgres' purpose-built primitive for
"queue table" semantics — it guarantees exactly one worker claims a given row
even with dozens of concurrent pollers, with no extra infrastructure. This is
the same technique used by real Postgres-backed job queues (e.g. `pgboss`,
`river`).

**Trade-off**: Optimistic locking would reduce lock contention further at
very high throughput, and a dedicated queue (SQS, Redis Streams, Kafka) would
scale further still — out of scope for the assignment's "efficient relational
schema" requirement, and unnecessary at intern-project throughput.

## 3. "Scheduled Jobs" modeled as a Job state, not a separate table

**Decision**: `cron_expression`, `run_at`, and `next_run_at` are columns on
`Job` rather than a standalone `ScheduledJob` table with its own lifecycle.

**Why**: A scheduled/recurring job still goes through the exact same
claim → execute → retry → complete pipeline as an immediate job. Splitting it
into a separate table would mean either (a) copying rows between tables when
a scheduled job "fires" (extra complexity, possible inconsistency), or (b)
constant joins to reconstitute a single job's history. Keeping it unified
means one query surface, one status enum, one execution history.

**Trade-off**: The `jobs` table carries a few always-null columns for
non-recurring jobs. Negligible cost in Postgres, and far simpler than
syncing two tables.

## 4. Retry strategy is data, not code

**Decision**: `RetryPolicy` stores `strategy` (fixed/linear/exponential) +
parameters per queue; the actual delay math lives in one pure function
(`services/retry.py`).

**Why**: Keeps retry behavior configurable per-queue without redeploying, and
the pure function is trivially unit-testable in isolation (see
`tests/test_retry_policy.py`) without touching the database.

## 5. Manual retry vs. automatic retry are the same underlying operation

**Decision**: The `/jobs/{id}/retry` endpoint (used by the dashboard for
failed/dead-lettered jobs) resets `retry_count` and re-queues, using the same
`queued` → claim → execute path as everything else, rather than a special
"manual execution" code path.

**Why**: Avoids a second, subtly-different execution path that could drift
from the automatic one and hide bugs.

## 6. Dashboard uses polling, not WebSockets

**Decision**: The React dashboard polls REST endpoints every 3-5 seconds
(`setInterval`) instead of a WebSocket/SSE push channel.

**Why**: WebSocket live updates were explicitly listed as a bonus feature.
Given the 2-hour budget, polling delivers ~all of the perceived
"live-ness" for a demo (sub-5-second latency) with a fraction of the
implementation and failure-mode complexity (reconnect logic, backpressure,
etc). This is a pragmatic, stated trade-off rather than an oversight.

## 7. UUID primary keys everywhere

**Decision**: Every table's PK is a client-generated UUIDv4.

**Why**: Multiple workers/processes insert concurrently (job executions, job
logs, heartbeats); UUIDs avoid any auto-increment sequence contention and
don't reveal row counts via the API. Downside is slightly larger index size
vs. bigint — an acceptable trade at this scale.

## 8. Organization as a lightweight multi-tenancy boundary

**Decision**: Every user belongs to exactly one `Organization`; all
authorization checks resolve project → organization → current user's org_id.

**Why**: The assignment lists "Organizations" as a top-level entity. Rather
than build full multi-org-membership (a user in many orgs, invitations,
org-switching UI), the first registered user becomes their org's sole
`admin`. This satisfies the schema requirement and demonstrates tenant
isolation (see `test_cross_org_isolation`) without RBAC/invite-flow scope
creep — RBAC is explicitly a bonus feature.

## 9. What was intentionally left out (bonus features)

Workflow dependencies between jobs, distributed locking beyond Postgres row
locks, queue sharding, full event-driven execution, WebSockets, fine-grained
RBAC, and AI-generated failure summaries were all explicitly bonus items in
the assignment. None are implemented, in favor of spending the available time
on correctness and polish of the core lifecycle, concurrency, retry/DLQ, and
observability requirements, which carry the majority of the evaluation
weight (75/100 marks).

## 10. Testing strategy

**Decision**: The default test suite runs against in-memory SQLite (fast, no
external dependencies) and covers auth, multi-tenancy isolation, project/queue
CRUD, job validation/lifecycle, pagination/filtering, and retry-delay math.
The *actual* concurrency guarantee (`FOR UPDATE SKIP LOCKED`) is verified by
a separate, explicitly-opt-in integration test
(`tests/test_concurrency_integration.py`) that runs multiple threads against
a real Postgres instance, because SQLite doesn't support that clause and
would give a false sense of safety if used to "test" it.
