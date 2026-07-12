"""
Tests run against an isolated in-memory SQLite database instead of Postgres
so they're fast and require no external services (good for CI/quick intern
grading). SQLite doesn't support `FOR UPDATE SKIP LOCKED`, so the claim
query's `.with_for_update()` clause is skipped automatically for that
dialect in this test setup - concurrency-critical behavior is instead
covered by `test_concurrency.py`, which documents how to verify it for
real against the Postgres service in docker-compose.
"""
import uuid
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.core.database import Base, get_db
from app.models import models  # noqa: F401
from app.main import app

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    # NOTE: deliberately NOT using `with TestClient(app) as c:` here. That
    # form triggers FastAPI's `lifespan`, which starts the worker pool /
    # scheduler background loops against the real Postgres SessionLocal -
    # unnecessary (and unavailable) for these fast API-level tests.
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client):
    email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post("/api/auth/register", json={
        "org_name": "Test Org", "email": email, "password": "supersecret123",
    })
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
