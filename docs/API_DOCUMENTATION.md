# API Documentation

Base URL (local dev): `http://localhost:8000`
Interactive Swagger UI: `http://localhost:8000/docs`
OpenAPI schema: `http://localhost:8000/openapi.json`

All endpoints except `/api/auth/register` and `/api/auth/login` require a
JWT bearer token:

```
Authorization: Bearer <token>
```

All requests/responses are JSON. Errors return:
```json
{ "detail": "human-readable message" }
```
with standard HTTP status codes (400 validation, 401 unauthorized, 404 not
found, 500 unexpected).

---

## Auth

### `POST /api/auth/register`
Creates a new Organization and its first (admin) User.

```json
// Request
{ "org_name": "Acme Inc", "email": "founder@acme.com", "password": "supersecret123" }

// 201 Response
{ "access_token": "eyJ...", "token_type": "bearer" }
```

### `POST /api/auth/login`
```json
// Request
{ "email": "founder@acme.com", "password": "supersecret123" }
// 200 Response
{ "access_token": "eyJ...", "token_type": "bearer" }
```

### `GET /api/auth/me`
Returns the current authenticated user.

---

## Projects

| Method | Path | Description |
|---|---|---|
| POST | `/api/projects` | Create a project `{name, description?}` |
| GET | `/api/projects` | List projects in your org |
| GET | `/api/projects/{project_id}` | Get one project |
| DELETE | `/api/projects/{project_id}` | Delete a project (cascades to queues/jobs) |

---

## Queues

| Method | Path | Description |
|---|---|---|
| POST | `/api/projects/{project_id}/queues` | Create queue: `{name, priority, concurrency_limit, retry_policy?}` |
| GET | `/api/projects/{project_id}/queues` | List queues for a project |
| GET | `/api/queues/{queue_id}` | Get one queue |
| PATCH | `/api/queues/{queue_id}` | Update `priority`/`concurrency_limit`/`is_paused`/`retry_policy` |
| POST | `/api/queues/{queue_id}/pause` | Pause the queue (no new claims) |
| POST | `/api/queues/{queue_id}/resume` | Resume the queue |
| GET | `/api/queues/{queue_id}/stats` | Counts by status: `{queued, running, completed, failed, dead_letter}` |
| DELETE | `/api/queues/{queue_id}` | Delete queue (cascades to jobs) |

**Retry policy object**
```json
{ "strategy": "exponential", "base_delay_seconds": 5, "max_delay_seconds": 300, "max_retries": 3 }
```
`strategy` is one of `fixed | linear | exponential`.

---

## Jobs

| Method | Path | Description |
|---|---|---|
| POST | `/api/queues/{queue_id}/jobs` | Create a job |
| POST | `/api/queues/{queue_id}/jobs/batch` | Create many jobs sharing one `batch_id` |
| GET | `/api/queues/{queue_id}/jobs` | Paginated + filterable job list |
| GET | `/api/jobs/{job_id}` | Job detail incl. execution history + logs |
| POST | `/api/jobs/{job_id}/retry` | Re-queue a `failed`/`dead_letter` job |
| POST | `/api/jobs/{job_id}/cancel` | Cancel a not-yet-running job |

### Create job
```json
// POST /api/queues/{queue_id}/jobs
{
  "name": "send-welcome-email",
  "job_type": "immediate",       // immediate | delayed | scheduled | recurring | batch
  "payload": { "to": "a@b.com" },
  "priority": 0,                  // optional override
  "run_at": "2026-07-12T10:00:00Z",     // required for delayed/scheduled
  "cron_expression": "*/5 * * * *",     // required for recurring
  "max_retries_override": null    // optional, overrides queue's retry policy
}
```

**Demo payload conventions** (simulated executor, see `services/worker_pool.py`):
- `{"duration_ms": 500}` — sleeps to simulate work.
- `{"fail": true}` — always fails (exercise retries → DLQ).
- `{"fail_until_attempt": 3}` — fails until that attempt number, then succeeds.

### List jobs (pagination + filtering)
```
GET /api/queues/{queue_id}/jobs?status=failed&job_type=immediate&page=1&page_size=20
```
```json
{ "items": [ /* JobOut[] */ ], "total": 42, "page": 1, "page_size": 20 }
```

### Batch job creation
```json
// POST /api/queues/{queue_id}/jobs/batch
{
  "name_prefix": "resize-image",
  "payloads": [{"file": "1.png"}, {"file": "2.png"}]
}
```
Returns an array of created jobs, all sharing one generated `batch_id`.

---

## Workers

| Method | Path | Description |
|---|---|---|
| GET | `/api/workers` | List all workers + status + last heartbeat |
| GET | `/api/workers/{worker_id}` | Get one worker |
| GET | `/api/workers/{worker_id}/current-job` | Currently claimed/running job, if any |

---

## Dashboard

| Method | Path | Description |
|---|---|---|
| GET | `/api/dashboard/health` | System-wide counts + throughput + worker counts |
| GET | `/api/dashboard/dead-letter` | All dead-lettered jobs for your org |
| GET | `/api/dashboard/throughput-series` | Completions per minute, last 30 min |

---

## Job lifecycle (status values)

```
queued -> claimed -> running -> completed
                          \--> failed --(retries remain)--> scheduled --> queued (loop)
                                     \--(retries exhausted)--> dead_letter
scheduled -> queued            (delayed/cron jobs, promoted by the Scheduler when due)
queued/scheduled -> cancelled  (manual cancel, before it starts running)
```
