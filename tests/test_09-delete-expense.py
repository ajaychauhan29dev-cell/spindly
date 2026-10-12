"""Tests for Step 9: Delete Expense (POST /expenses/<id>/delete).

Written from .claude/specs/09-delete-expense.md.
"""
import re

import pytest

from database import db
from database import queries

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"
MISSING_ID = 999999


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()
    from app import app

    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def logged_in(client):
    client.post("/login", data={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    return client


def _demo_user_id():
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT id FROM users WHERE email = ?", (DEMO_EMAIL,)
        ).fetchone()["id"]
    finally:
        conn.close()


def _make_expense(user_id, amount=42.5, category="Transport",
                  expense_date="2026-02-14", description="Original desc"):
    conn = db.get_db()
    try:
        cur = conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, expense_date, description),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _row(expense_id):
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
    finally:
        conn.close()


def _count_expenses():
    conn = db.get_db()
    try:
        return conn.execute("SELECT COUNT(*) AS c FROM expenses").fetchone()["c"]
    finally:
        conn.close()


@pytest.fixture
def expense_id(client):
    """An expense owned by the demo user."""
    return _make_expense(_demo_user_id())


@pytest.fixture
def other_user_id(client):
    return db.create_user("Other", "other@example.com", "pw12345")


@pytest.fixture
def other_expense_id(other_user_id):
    return _make_expense(other_user_id, 77.0, "Bills", "2026-01-10", "Other's secret")


def _url(eid):
    return f"/expenses/{eid}/delete"


# ---------------------------------------------------------------------------
# delete_expense unit tests
# ---------------------------------------------------------------------------
class TestDeleteExpenseHelper:
    def test_correct_owner_removes_row(self, client, expense_id):
        queries.delete_expense(expense_id, _demo_user_id())
        assert _row(expense_id) is None, "Row should be removed for the owner"

    def test_correct_owner_only_removes_target_row(self, client, expense_id):
        other_id = _make_expense(_demo_user_id(), description="Keep me")
        before = _count_expenses()
        queries.delete_expense(expense_id, _demo_user_id())
        assert _count_expenses() == before - 1, "Exactly one row should be deleted"
        assert _row(other_id) is not None, "Other rows must be untouched"

    def test_wrong_user_leaves_row_and_raises_nothing(self, client, expense_id, other_user_id):
        queries.delete_expense(expense_id, other_user_id)
        assert _row(expense_id) is not None, "Row must remain for non-owner"

    def test_nonexistent_id_raises_nothing_and_db_unchanged(self, client, expense_id):
        before = _count_expenses()
        queries.delete_expense(MISSING_ID, _demo_user_id())
        assert _count_expenses() == before, "DB should be unchanged"


# ---------------------------------------------------------------------------
# Route tests
# ---------------------------------------------------------------------------
class TestDeleteExpenseRoute:
    def test_unauthenticated_redirects_to_login(self, client, expense_id):
        resp = client.post(_url(expense_id))
        assert resp.status_code == 302, "Expected redirect"
        assert "/login" in resp.headers["Location"]

    def test_unauthenticated_does_not_delete(self, client, expense_id):
        client.post(_url(expense_id))
        assert _row(expense_id) is not None, "Logged-out user must not delete"

    def test_own_expense_redirects_to_profile(self, logged_in, expense_id):
        resp = logged_in.post(_url(expense_id))
        assert resp.status_code == 302
        loc = resp.headers["Location"].split("?")[0]
        assert loc.endswith("/profile"), f"Expected /profile, got {loc}"

    def test_own_expense_row_removed(self, logged_in, expense_id):
        logged_in.post(_url(expense_id))
        assert _row(expense_id) is None, "Row should be gone from DB"

    def test_own_expense_not_shown_on_profile_after_delete(self, logged_in, client):
        eid = _make_expense(_demo_user_id(), description="UniqueDeleteMarker123")
        assert b"UniqueDeleteMarker123" in logged_in.get("/profile").data
        logged_in.post(_url(eid))
        resp = logged_in.get("/profile")
        assert b"UniqueDeleteMarker123" not in resp.data

    def test_own_expense_follow_redirect_renders_profile(self, logged_in, expense_id):
        resp = logged_in.post(_url(expense_id), follow_redirects=True)
        assert resp.status_code == 200

    def test_other_users_expense_returns_404(self, logged_in, other_expense_id):
        resp = logged_in.post(_url(other_expense_id))
        assert resp.status_code == 404

    def test_other_users_expense_row_remains(self, logged_in, other_expense_id):
        logged_in.post(_url(other_expense_id))
        assert _row(other_expense_id) is not None, "Other user's row must remain"

    def test_nonexistent_id_returns_404(self, logged_in):
        resp = logged_in.post(_url(MISSING_ID))
        assert resp.status_code == 404

    def test_nonexistent_id_does_not_change_db(self, logged_in, expense_id):
        before = _count_expenses()
        logged_in.post(_url(MISSING_ID))
        assert _count_expenses() == before

    def test_second_delete_of_same_id_returns_404(self, logged_in, expense_id):
        logged_in.post(_url(expense_id))
        resp = logged_in.post(_url(expense_id))
        assert resp.status_code == 404

    def test_non_integer_id_returns_404(self, logged_in):
        resp = logged_in.post("/expenses/abc/delete")
        assert resp.status_code == 404

    def test_get_logged_in_returns_405(self, logged_in, expense_id):
        resp = logged_in.get(_url(expense_id))
        assert resp.status_code == 405
        assert _row(expense_id) is not None, "GET must not delete"

    def test_get_logged_out_returns_405(self, client, expense_id):
        resp = client.get(_url(expense_id))
        assert resp.status_code == 405

    def test_get_nonexistent_returns_405(self, logged_in):
        assert logged_in.get(_url(MISSING_ID)).status_code == 405

    @pytest.mark.parametrize("method", ["put", "patch", "delete"])
    def test_other_methods_not_allowed(self, logged_in, expense_id, method):
        resp = getattr(logged_in, method)(_url(expense_id))
        assert resp.status_code == 405
        assert _row(expense_id) is not None


# ---------------------------------------------------------------------------
# Profile page UI
# ---------------------------------------------------------------------------
class TestProfileActions:
    def test_profile_shows_delete_form_for_expense(self, logged_in, expense_id):
        html = logged_in.get("/profile").get_data(as_text=True)
        assert f"/expenses/{expense_id}/delete" in html, "Delete action missing"
        assert "Delete" in html

    def test_profile_shows_edit_link_for_expense(self, logged_in, expense_id):
        html = logged_in.get("/profile").get_data(as_text=True)
        assert f"/expenses/{expense_id}/edit" in html, "Edit action missing"
        assert "Edit" in html

    def test_delete_form_uses_post(self, logged_in, expense_id):
        html = logged_in.get("/profile").get_data(as_text=True)
        pattern = (
            r'<form[^>]*method="POST"[^>]*/expenses/%d/delete'
            r'|<form[^>]*/expenses/%d/delete[^>]*method="POST"'
        ) % (expense_id, expense_id)
        assert re.search(pattern, html, re.IGNORECASE), "Delete must be a POST form"

    def test_delete_form_has_confirm_prompt(self, logged_in, expense_id):
        html = logged_in.get("/profile").get_data(as_text=True)
        assert "confirm(" in html, "Expected browser confirm() guard"

    def test_every_row_has_edit_and_delete(self, logged_in, expense_id):
        second = _make_expense(_demo_user_id(), description="Second row")
        html = logged_in.get("/profile").get_data(as_text=True)
        for eid in (expense_id, second):
            assert f"/expenses/{eid}/delete" in html
            assert f"/expenses/{eid}/edit" in html

    def test_profile_does_not_show_delete_for_other_users_expense(
        self, logged_in, other_expense_id
    ):
        html = logged_in.get("/profile").get_data(as_text=True)
        assert f"/expenses/{other_expense_id}/delete" not in html
