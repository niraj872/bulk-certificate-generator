import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_bulk_certificates.db?check_same_thread=false")
os.environ.setdefault("STORAGE_PATH", "./test_storage")
os.environ.setdefault("MAX_RECIPIENTS", "1000")
os.environ.setdefault("WORKER_POLL_SECONDS", "0.1")
os.environ.setdefault("JOB_STALE_SECONDS", "30")

import pytest
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app


@pytest.fixture(autouse=True)
def reset_database(tmp_path, monkeypatch):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    storage = tmp_path / "storage"
    storage.mkdir()
    monkeypatch.setattr("app.workers.worker.settings.storage_path", str(storage))
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
