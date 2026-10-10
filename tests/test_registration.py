import sqlite3

import pytest
from werkzeug.security import check_password_hash

from database import db


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    from app import app

    app.config["TESTING"] = True
    return app.test_client()


def _form(**overrides):
    data = {
        "name": "Test User",
        "email": "test@example.com",
        "password": "secret123",
        "confirm_password": "secret123",
    }
    data.update(overrides)
    return data


def _users(email="test@example.com"):
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchall()
    finally:
        conn.close()


def test_get_register_renders_form(client):
    resp = client.get("/register")
    assert resp.status_code == 200
    for field in ("name", "email", "password", "confirm_password"):
        assert f'name="{field}"' in resp.get_data(as_text=True)


def test_valid_registration_redirects_and_hashes(client):
    resp = client.post("/register", data=_form())
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    rows = _users()
    assert len(rows) == 1
    assert rows[0]["password_hash"] != "secret123"
    assert check_password_hash(rows[0]["password_hash"], "secret123")


def test_success_message_shown_on_login(client):
    resp = client.post("/register", data=_form(), follow_redirects=True)
    assert b"Account created" in resp.data


def test_password_mismatch(client):
    resp = client.post("/register", data=_form(confirm_password="other"))
    assert resp.status_code == 200
    assert b"Passwords do not match" in resp.data
    assert _users() == []


def test_duplicate_email(client):
    client.post("/register", data=_form())
    resp = client.post("/register", data=_form(email="TEST@example.com"))
    assert resp.status_code == 200
    assert b"Email already registered" in resp.data
    assert len(_users()) == 1


@pytest.mark.parametrize(
    "field", ["name", "email", "password", "confirm_password"]
)
def test_empty_field(client, field):
    resp = client.post("/register", data=_form(**{field: ""}))
    assert resp.status_code == 200
    assert b"All fields are required" in resp.data
    assert _users() == []


def test_unsupported_method(client):
    assert client.put("/register").status_code == 405


def test_create_user_duplicate_raises(client):
    db.create_user("A", "a@example.com", "pw")
    with pytest.raises(sqlite3.IntegrityError):
        db.create_user("B", "a@example.com", "pw")
