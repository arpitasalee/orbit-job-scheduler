# Orbit — Distributed Job Scheduler

A production-inspired, monolithic job scheduling platform: authentication,
projects, queues, jobs (immediate/delayed/scheduled/recurring/batch),
atomic job claiming, configurable retry policies, a Dead Letter Queue, and a
live-updating dashboard.

**Stack**: FastAPI · PostgreSQL · SQLAlchemy · Alembic · JWT · React · Vite ·
TailwindCSS · Docker Compose.

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — system architecture diagram
- [`docs/ER_DIAGRAM.md`](docs/ER_DIAGRAM.md) — database schema + rationale
- [`docs/DESIGN_DECISIONS.md`](docs/DESIGN_DECISIONS.md) — trade-offs explained
- [`docs/API_DOCUMENTATION.md`](docs/API_DOCUMENTATION.md) — full API reference

## Quick start (Docker — recommended)

Requires Docker + Docker Compose.

```bash
docker compose up --build
```

This starts:
- **Postgres** on `localhost:5432`
- **Backend** (FastAPI + worker pool + scheduler, all in one process) on
  `localhost:8000` — migrations run automatically on container start
- **Frontend** (React dashboard) on `localhost:5173`

Then:
1. Open `http://localhost:5173`
2. Register an organization + account
3. Create a Project → a Queue → a Job, and watch it get picked up by a
   worker within a couple of seconds (dashboard auto-refreshes)

Try creating a job with payload `{"fail": true}` to see it retry with
backoff and eventually land in the Dead Letter Queue.

## Manual / local development setup

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Start Postgres however you like, e.g.:
docker run -d --name orbit-pg -e POSTGRES_USER=scheduler -e POSTGRES_PASSWORD=scheduler \
  -e POSTGRES_DB=scheduler_db -p 5432:5432 postgres:16-alpine

cp .env.example .env   # adjust DATABASE_URL if needed
alembic upgrade head
uvicorn app.main:app --reload
```
API docs: `http://localhost:8000/docs`

### Frontend
```bash
cd frontend
npm install
cp .env.example .env   # points at http://localhost:8000 by default
npm run dev
```
Dashboard: `http://localhost:5173`

## Running tests

```bash
cd backend
pip install -r requirements.txt
pytest -v
```
Runs against an isolated in-memory SQLite DB — no external services needed.
28 tests cover auth, multi-tenant isolation, queue/retry-policy config, job
validation & lifecycle, pagination/filtering, and retry backoff math.

To verify the *actual* concurrency guarantee (atomic claiming under real
parallel load) against Postgres:
```bash
docker compose up -d db
export DATABASE_URL=postgresql://scheduler:scheduler@localhost:5432/scheduler_db
RUN_INTEGRATION=1 pytest tests/test_concurrency_integration.py -v
```

## Project layout

```
job-scheduler/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app, lifespan (starts worker pool + scheduler)
│   │   ├── core/                   # config, db session, JWT/password utils
│   │   ├── models/models.py        # SQLAlchemy models (full schema)
│   │   ├── schemas/schemas.py       # Pydantic request/response schemas
│   │   ├── api/
│   │   │   ├── deps.py             # auth + ownership dependencies
│   │   │   └── routers/            # auth, projects, queues, jobs, workers, dashboard
│   │   └── services/
│   │       ├── worker_pool.py      # atomic claim, execution, retry/DLQ, heartbeats
│   │       ├── scheduler.py        # promotes due delayed/scheduled/recurring jobs
│   │       └── retry.py            # backoff strategy math (pure functions)
│   ├── alembic/                    # migrations
│   ├── tests/                      # pytest suite
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/                  # Login, Register, Dashboard, Projects, ProjectDetail,
│   │   │                           # QueueDetail, JobDetail, Workers, DeadLetter
│   │   ├── components/              # Navbar, StatusBadge, StatCard
│   │   ├── context/AuthContext.jsx
│   │   └── api/client.js           # fetch wrapper w/ JWT
│   └── Dockerfile
├── docs/                           # architecture, ER diagram, design decisions, API docs
└── docker-compose.yml
```

## Core features implemented

- **Auth**: JWT-based register/login, org-scoped multi-tenancy, password hashing (bcrypt)
- **Projects & Queues**: CRUD, priority, concurrency limits, pause/resume, per-queue stats
- **Retry policies**: fixed / linear / exponential backoff, configurable per queue
- **Jobs**: immediate, delayed, scheduled (one-off), recurring (cron via `croniter`), batch
- **Reliability**: atomic claiming via `SELECT ... FOR UPDATE SKIP LOCKED` (no double-execution),
  automatic retries with backoff, Dead Letter Queue after retries exhausted, manual re-queue
- **Observability**: execution history per attempt, structured job logs, worker heartbeats +
  staleness detection, system health + throughput metrics
- **Dashboard**: queue management, job explorer with filters/pagination, job detail w/ logs,
  worker monitor, Dead Letter Queue view, live-ish polling updates
- **API**: validation, pagination, filtering, structured errors, interactive Swagger docs
- **Tests**: 28 automated tests (auth, isolation, CRUD, lifecycle, pagination, retry math) +
  a documented concurrency integration test against real Postgres

## Known limitations (by design, see DESIGN_DECISIONS.md)

- Worker pool runs in-process (not separate containers) — the claiming logic is
  process-count-agnostic and would work unchanged across real worker containers.
- Dashboard uses polling, not WebSockets (bonus feature, out of scope).
- No workflow dependencies / queue sharding / RBAC — all explicitly bonus features.
