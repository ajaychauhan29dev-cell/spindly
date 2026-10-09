import sqlite3
from datetime import date

import pytest
from werkzeug.security import check_password_hash

from database import db

CATEGORIES = {
    "Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other",
}


@pytest.fixture
def seeded_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()


def test_tables_exist(seeded_db):
    conn = db.get_db()
    names = {
        r["name"]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    conn.close()
    assert {"users", "expenses"} <= names


def test_demo_user_seeded_with_hashed_password(seeded_db):
    conn = db.get_db()
    users = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    assert len(users) == 1
    assert users[0]["email"] == "demo@spendly.com"
    assert users[0]["password_hash"] != "demo123"
    assert check_password_hash(users[0]["password_hash"], "demo123")


def test_expenses_seeded(seeded_db):
    conn = db.get_db()
    rows = conn.execute("SELECT * FROM expenses").fetchall()
    conn.close()
    assert len(rows) == 8
    assert {r["category"] for r in rows} == CATEGORIES
    month = date.today().strftime("%Y-%m")
    assert all(r["date"].startswith(month) for r in rows)
    assert all(isinstance(r["amount"], float) for r in rows)


def test_seed_is_idempotent(seeded_db):
    db.init_db()
    db.seed_db()
    conn = db.get_db()
    users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    expenses = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    conn.close()
    assert (users, expenses) == (1, 8)


def test_foreign_keys_enforced(seeded_db):
    conn = db.get_db()
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date) "
            "VALUES (?, ?, ?, ?)",
            (999, 1.0, "Food", "2026-01-01"),
        )
    conn.close()


def test_duplicate_email_rejected(seeded_db):
    conn = db.get_db()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Other", "demo@spendly.com", "x"),
        )
    conn.close()
