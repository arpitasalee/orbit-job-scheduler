import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routers import auth, projects, queues, jobs, workers, dashboard
from app.services.worker_pool import worker_pool
from app.services.scheduler import scheduler_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: bring up the in-process worker pool + scheduler loop.
    await worker_pool.start()
    scheduler_service.start()
    logger.info("Application startup complete")
    yield
    # Shutdown: drain workers gracefully (finish in-flight jobs, no new claims).
    logger.info("Application shutting down - draining workers...")
    await scheduler_service.stop()
    await worker_pool.stop()


app = FastAPI(
    title="Distributed Job Scheduler API",
    description="A production-inspired job scheduling platform (internship project).",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo-scoped; restrict to the frontend origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(queues.router)
app.include_router(jobs.router)
app.include_router(workers.router)
app.include_router(dashboard.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
