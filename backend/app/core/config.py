"""
Centralized application configuration loaded from environment variables.
Keeping all tunables in one place makes the service 12-factor compliant
and simplifies Docker/CI configuration.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://scheduler:scheduler@localhost:5432/scheduler_db"

    # JWT Auth
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24h, fine for an intern demo

    # Worker pool (in-process, simulates a distributed worker fleet)
    WORKER_POOL_SIZE: int = 3
    WORKER_POLL_INTERVAL_SECONDS: float = 1.0
    WORKER_HEARTBEAT_INTERVAL_SECONDS: float = 5.0
    WORKER_STALE_AFTER_SECONDS: int = 30

    # Scheduler (handles delayed / cron / recurring jobs)
    SCHEDULER_POLL_INTERVAL_SECONDS: float = 1.0

    class Config:
        env_file = ".env"


settings = Settings()
