"""Tests for Step 8: Edit Expense (GET/POST /expenses/<id>/edit).

Written from .claude/specs/08-edit-expense.md.
"""
import re

import pytest

from database import db
from database import queries

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"
CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]
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
    """Insert an expense and return its id."""
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
def other_expense_id(client):
    """An expense owned by a different user."""
    other = db.create_user("Other", "other@example.com", "pw12345")
    return _make_expense(other, 77.0, "Bills", "2026-01-10", "Other's secret")


def _url(eid):
    return f"/expenses/{eid}/edit"


def _valid(**overrides):
    data = {
        "amount": "99.0",
        "category": "Food",
        "date": "2026-03-20",
        "description": "Updated desc",
    }
    data.update(overrides)
    return data


def _is_login_redirect(response):
    return response.status_code == 302 and "/login" in response.headers["Location"]


def _is_profile_redirect(response):
    loc = response.headers.get("Location", "")
    return response.status_code == 302 and loc.split("?")[0].endswith("/profile")


def _has_error(html):
    return "auth-error" in html


# ---------------------------------------------------------------------------
# Query helper unit tests
# ---------------------------------------------------------------------------
class TestGetExpenseById:
    def test_correct_user_returns_row(self, client, expense_id):
        row = queries.get_expense_by_id(expense_id, _demo_user_id())
        assert row is not None, "Owner should get the row"
        assert row["amount"] == pytest.approx(42.5)
        assert row["category"] == "Transport"
        assert row["date"] == "2026-02-14"
        assert row["description"] == "Original desc"

    def test_wrong_user_returns_none(self, client, expense_id):
        other = db.create_user("Other", "other@example.com", "pw12345")
        assert queries.get_expense_by_id(expense_id, other) is None

    def test_nonexistent_id_returns_none(self, client):
        assert queries.get_expense_by_id(MISSING_ID, _demo_user_id()) is None


class TestUpdateExpense:
    def test_correct_user_updates_row(self, client, expense_id):
        queries.update_expense(
            expense_id, _demo_user_id(), 99.0, "Food", "2026-03-20", "New"
        )
        row = _row(expense_id)
        assert row["amount"] == pytest.approx(99.0)
        assert row["category"] == "Food"
        assert row["date"] == "2026-03-20"
        assert row["description"] == "New"

    def test_correct_user_returns_rowcount_one(self, client, expense_id):
        result = queries.update_expense(
            expense_id, _demo_user_id(), 99.0, "Food", "2026-03-20", "New"
        )
        assert result == 1

    def test_wrong_user_leaves_row_unchanged_and_returns_zero(
        self, client, other_expense_id
    ):
        before = dict(_row(other_expense_id))
        result = queries.update_expense(
            other_expense_id, _demo_user_id(), 1.0, "Food", "2030-01-01", "Hacked"
        )
        assert result == 0, "No rows should be affected"
        assert dict(_row(other_expense_id)) == before

    def test_none_description_stores_null(self, client, expense_id):
        queries.update_expense(
            expense_id, _demo_user_id(), 5.0, "Other", "2026-03-20", None
        )
        assert _row(expense_id)["description"] is None

    def test_get_recent_transactions_includes_id(self, client, expense_id):
        txs = queries.get_recent_transactions(_demo_user_id(), limit=100)
        assert txs, "Expected transactions"
        assert all("id" in dict(t) or "id" in t.keys() for t in txs)
        assert expense_id in [t["id"] for t in txs]


# ---------------------------------------------------------------------------
# Auth guards
# ---------------------------------------------------------------------------
class TestAuthGuard:
    def test_get_unauthenticated_redirects_to_login(self, client, expense_id):
        assert _is_login_redirect(client.get(_url(expense_id)))

    def test_post_unauthenticated_redirects_to_login(self, client, expense_id):
        assert _is_login_redirect(client.post(_url(expense_id), data=_valid()))

    def test_post_unauthenticated_does_not_modify_row(self, client, expense_id):
        before = dict(_row(expense_id))
        client.post(_url(expense_id), data=_valid())
        assert dict(_row(expense_id)) == before


# ---------------------------------------------------------------------------
# GET form
# ---------------------------------------------------------------------------
class TestGetForm:
    def test_own_expense_returns_200(self, logged_in, expense_id):
        assert logged_in.get(_url(expense_id)).status_code == 200

    def test_other_users_expense_returns_404(self, logged_in, other_expense_id):
        assert logged_in.get(_url(other_expense_id)).status_code == 404

    def test_nonexistent_expense_returns_404(self, logged_in):
        assert logged_in.get(_url(MISSING_ID)).status_code == 404

    def test_other_users_data_not_leaked_in_404(self, logged_in, other_expense_id):
        html = logged_in.get(_url(other_expense_id)).get_data(as_text=True)
        assert "Other's secret" not in html

    def test_form_posts_to_edit_url(self, logged_in, expense_id):
        html = logged_in.get(_url(expense_id)).get_data(as_text=True)
        form = re.search(r"<form\b[^>]*>", html, re.I)
        assert form, "Expected a form"
        assert re.search(r'method\s*=\s*["\']post["\']', form.group(0), re.I)
        assert f"/expenses/{expense_id}/edit" in form.group(0)

    def test_form_prefilled_with_current_values(self, logged_in, expense_id):
        html = logged_in.get(_url(expense_id)).get_data(as_text=True)
        amount = re.search(r"<input\b[^>]*name\s*=\s*[\"']amount[\"'][^>]*>", html, re.I)
        assert amount, "Expected amount input"
        assert re.search(r'value\s*=\s*["\']42\.5', amount.group(0)), amount.group(0)
        date_tag = re.search(r"<input\b[^>]*name\s*=\s*[\"']date[\"'][^>]*>", html, re.I)
        assert date_tag and "2026-02-14" in date_tag.group(0)
        desc = re.search(
            r"<input\b[^>]*name\s*=\s*[\"']description[\"'][^>]*>", html, re.I
        )
        assert desc and "Original desc" in desc.group(0)

    def test_form_amount_input_attributes(self, logged_in, expense_id):
        html = logged_in.get(_url(expense_id)).get_data(as_text=True)
        t = re.search(r"<input\b[^>]*name\s*=\s*[\"']amount[\"'][^>]*>", html, re.I).group(0)
        assert "number" in t and "0.01" in t and "required" in t

    def test_form_description_max_length_200(self, logged_in, expense_id):
        html = logged_in.get(_url(expense_id)).get_data(as_text=True)
        t = re.search(
            r"<input\b[^>]*name\s*=\s*[\"']description[\"'][^>]*>", html, re.I
        ).group(0)
        assert re.search(r'maxlength\s*=\s*["\']?200', t, re.I)

    def test_category_select_has_seven_options(self, logged_in, expense_id):
        html = logged_in.get(_url(expense_id)).get_data(as_text=True)
        select = re.search(
            r"<select\b[^>]*name\s*=\s*[\"']category[\"'][^>]*>(.*?)</select>",
            html, re.S | re.I,
        )
        assert select, "Expected category select"
        options = re.findall(
            r"<option\b(?![^>]*\bdisabled\b)[^>]*>(.*?)</option>", select.group(1), re.S
        )
        assert [o.strip() for o in options] == CATEGORIES

    def test_current_category_preselected(self, logged_in, expense_id):
        html = logged_in.get(_url(expense_id)).get_data(as_text=True)
        selected = re.findall(r"<option\b[^>]*\bselected\b[^>]*>[^<]*", html, re.I)
        assert len(selected) == 1, f"Exactly one option selected, got {selected}"
        assert "Transport" in selected[0]

    @pytest.mark.parametrize("category", CATEGORIES)
    def test_each_category_preselected_correctly(self, logged_in, category):
        eid = _make_expense(_demo_user_id(), category=category)
        html = logged_in.get(_url(eid)).get_data(as_text=True)
        selected = re.findall(r"<option\b[^>]*\bselected\b[^>]*>[^<]*", html, re.I)
        assert len(selected) == 1 and category in selected[0]

    def test_has_save_changes_button_and_cancel_link(self, logged_in, expense_id):
        html = logged_in.get(_url(expense_id)).get_data(as_text=True)
        assert "Save Changes" in html
        assert re.search(r'<a\b[^>]*href\s*=\s*["\'][^"\']*/profile["\']', html)

    def test_extends_base_layout(self, logged_in, expense_id):
        html = logged_in.get(_url(expense_id)).get_data(as_text=True)
        assert "<nav" in html.lower()

    def test_no_wrong_currency_symbols(self, logged_in, expense_id):
        html = logged_in.get(_url(expense_id)).get_data(as_text=True)
        assert "£" not in html and "$" not in html


# ---------------------------------------------------------------------------
# POST success
# ---------------------------------------------------------------------------
class TestPostSuccess:
    def test_valid_redirects_to_profile(self, logged_in, expense_id):
        response = logged_in.post(_url(expense_id), data=_valid())
        assert _is_profile_redirect(response), response.headers.get("Location")

    def test_valid_updates_database(self, logged_in, expense_id):
        logged_in.post(_url(expense_id), data=_valid(
            amount="99.0", category="Health", date="2026-03-20", description="Doc"))
        row = _row(expense_id)
        assert row["amount"] == pytest.approx(99.0)
        assert row["category"] == "Health"
        assert row["date"] == "2026-03-20"
        assert row["description"] == "Doc"

    def test_valid_does_not_create_new_row(self, logged_in, expense_id):
        before = _count_expenses()
        logged_in.post(_url(expense_id), data=_valid())
        assert _count_expenses() == before

    def test_valid_does_not_touch_other_rows(self, logged_in, expense_id):
        sibling = _make_expense(_demo_user_id(), description="sibling")
        before = dict(_row(sibling))
        logged_in.post(_url(expense_id), data=_valid())
        assert dict(_row(sibling)) == before

    def test_follow_redirect_shows_updated_values_on_profile(self, logged_in, expense_id):
        response = logged_in.post(
            _url(expense_id),
            data=_valid(amount="1234.56", description="Zebra edit"),
            follow_redirects=True,
        )
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "Zebra edit" in body
        assert "Original desc" not in body
        assert "₹" in body and "£" not in body

    @pytest.mark.parametrize("category", CATEGORIES)
    def test_each_valid_category_accepted(self, logged_in, expense_id, category):
        response = logged_in.post(_url(expense_id), data=_valid(category=category))
        assert _is_profile_redirect(response)
        assert _row(expense_id)["category"] == category

    def test_no_description_field_stores_null(self, logged_in, expense_id):
        data = _valid()
        del data["description"]
        response = logged_in.post(_url(expense_id), data=data)
        assert _is_profile_redirect(response)
        assert _row(expense_id)["description"] is None

    @pytest.mark.parametrize("blank", ["", "   ", "\t "])
    def test_blank_description_stores_null(self, logged_in, expense_id, blank):
        response = logged_in.post(_url(expense_id), data=_valid(description=blank))
        assert _is_profile_redirect(response)
        assert _row(expense_id)["description"] is None

    def test_description_is_stripped(self, logged_in, expense_id):
        logged_in.post(_url(expense_id), data=_valid(description="  padded  "))
        assert _row(expense_id)["description"] == "padded"

    def test_sql_injection_description_stored_literally(self, logged_in, expense_id):
        payload = "x'); DROP TABLE expenses;--"
        response = logged_in.post(_url(expense_id), data=_valid(description=payload))
        assert _is_profile_redirect(response)
        assert _row(expense_id)["description"] == payload
        assert _count_expenses() > 0


# ---------------------------------------------------------------------------
# POST ownership / existence
# ---------------------------------------------------------------------------
class TestPostOwnership:
    def test_other_users_expense_returns_404(self, logged_in, other_expense_id):
        response = logged_in.post(_url(other_expense_id), data=_valid())
        assert response.status_code == 404

    def test_other_users_expense_not_modified(self, logged_in, other_expense_id):
        before = dict(_row(other_expense_id))
        logged_in.post(_url(other_expense_id), data=_valid())
        assert dict(_row(other_expense_id)) == before

    def test_nonexistent_expense_returns_404(self, logged_in):
        assert logged_in.post(_url(MISSING_ID), data=_valid()).status_code == 404


# ---------------------------------------------------------------------------
# POST validation errors
# ---------------------------------------------------------------------------
class TestPostValidation:
    @pytest.mark.parametrize(
        "overrides",
        [
            {"amount": ""},
            {"amount": "0"},
            {"amount": "0.00"},
            {"amount": "-5"},
            {"amount": "abc"},
            {"amount": "12abc"},
            {"category": ""},
            {"category": "Groceries"},
            {"category": "food"},
            {"category": "'; DROP TABLE expenses;--"},
            {"date": ""},
            {"date": "not-a-date"},
            {"date": "2026-13-01"},
            {"date": "2026-02-30"},
            {"date": "20/03/2026"},
        ],
        ids=lambda o: "-".join(f"{k}={str(v)[:12]}" for k, v in o.items()),
    )
    def test_invalid_rerenders_form_with_error_and_no_change(
        self, logged_in, expense_id, overrides
    ):
        before = dict(_row(expense_id))
        response = logged_in.post(_url(expense_id), data=_valid(**overrides))
        assert response.status_code == 200, "Invalid input must re-render form"
        html = response.get_data(as_text=True)
        assert "<form" in html, "Form should be re-rendered"
        assert _has_error(html), "Expected an auth-error message"
        assert dict(_row(expense_id)) == before, "Row must not change"

    @pytest.mark.parametrize("field", ["amount", "category", "date"])
    def test_missing_required_field_rerenders_with_error(
        self, logged_in, expense_id, field
    ):
        data = _valid()
        del data[field]
        before = dict(_row(expense_id))
        response = logged_in.post(_url(expense_id), data=data)
        assert response.status_code == 200
        assert _has_error(response.get_data(as_text=True))
        assert dict(_row(expense_id)) == before

    def test_empty_body_rerenders_form(self, logged_in, expense_id):
        before = dict(_row(expense_id))
        response = logged_in.post(_url(expense_id), data={})
        assert response.status_code == 200
        assert dict(_row(expense_id)) == before

    def test_error_shows_submitted_values_not_original(self, logged_in, expense_id):
        response = logged_in.post(
            _url(expense_id),
            data=_valid(amount="0", description="Keep me please", date="2026-05-05"),
        )
        html = response.get_data(as_text=True)
        assert response.status_code == 200
        assert "Keep me please" in html, "Submitted description retained"
        assert "2026-05-05" in html, "Submitted date retained"
        assert "Original desc" not in html, "Original values must not override"
        assert "2026-02-14" not in html

    def test_error_preserves_submitted_amount(self, logged_in, expense_id):
        response = logged_in.post(
            _url(expense_id), data=_valid(category="Nope", amount="77.25")
        )
        assert "77.25" in response.get_data(as_text=True)

    def test_error_preserves_submitted_category_selection(self, logged_in, expense_id):
        response = logged_in.post(
            _url(expense_id), data=_valid(amount="", category="Shopping")
        )
        html = response.get_data(as_text=True)
        selected = re.findall(r"<option\b[^>]*\bselected\b[^>]*>[^<]*", html, re.I)
        assert len(selected) == 1 and "Shopping" in selected[0], selected


# ---------------------------------------------------------------------------
# Profile page Edit links
# ---------------------------------------------------------------------------
class TestProfileEditLinks:
    def test_profile_has_actions_header(self, logged_in):
        html = logged_in.get("/profile").get_data(as_text=True)
        assert re.search(r"<th\b[^>]*>\s*Actions\s*</th>", html, re.I)

    def test_profile_row_has_edit_link_to_correct_url(self, logged_in, expense_id):
        html = logged_in.get("/profile").get_data(as_text=True)
        assert re.search(
            rf'<a\b[^>]*href\s*=\s*["\'][^"\']*/expenses/{expense_id}/edit["\'][^>]*>'
            r"\s*Edit\s*</a>",
            html,
        ), "Expected Edit link for the new expense"

    def test_profile_does_not_link_to_other_users_expense(
        self, logged_in, other_expense_id
    ):
        html = logged_in.get("/profile").get_data(as_text=True)
        assert f"/expenses/{other_expense_id}/edit" not in html
