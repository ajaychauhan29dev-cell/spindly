import pytest

from database import db


@pytest.fixture
def seeded_db(tmp_path, monkeypatch):
    """Temp DB with the demo user and 8 seed expenses; returns the demo user id."""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()
    return db.get_user_by_email("demo@spendly.com")["id"]


@pytest.fixture
def empty_user(tmp_path, monkeypatch):
    """Temp DB with one user who has no expenses; returns that user's id."""
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test_empty.db"))
    db.init_db()
    return db.create_user("Empty User", "empty@example.com", "secret123")
