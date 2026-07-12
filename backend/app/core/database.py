from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

# pool_pre_ping avoids stale-connection errors after DB restarts/network blips.
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a DB session per-request and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
