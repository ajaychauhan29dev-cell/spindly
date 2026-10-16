import sqlite3

import pytest

import app as app_module
from database import db


@pytest.fixture
def client(seeded_db):
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert body["users"] >= 1
    assert body["expenses"] >= 1


def test_health_returns_503_when_db_fails(client, monkeypatch):
    def boom():
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(app_module, "check_db", boom)
    resp = client.get("/health")
    assert resp.status_code == 503
    assert resp.get_json() == {"status": "error", "db": "unreachable"}


def test_check_db_counts(seeded_db):
    counts = db.check_db()
    assert counts["users"] == 1
    assert counts["expenses"] == 8
