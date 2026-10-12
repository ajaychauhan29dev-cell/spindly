"""Tests for Step 7: Add Expense (GET/POST /expenses/add).

Written from .claude/specs/07-add-expense.md.
"""
import re
from datetime import date

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
ADD_URL = "/expenses/add"


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
        row = conn.execute(
            "SELECT id FROM users WHERE email = ?", (DEMO_EMAIL,)
        ).fetchone()
        return row["id"]
    finally:
        conn.close()


def _count_expenses():
    conn = db.get_db()
    try:
        return conn.execute("SELECT COUNT(*) AS c FROM expenses").fetchone()["c"]
    finally:
        conn.close()


def _find_expenses(**filters):
    clauses = " AND ".join(f"{k} = ?" for k in filters) or "1=1"
    conn = db.get_db()
    try:
        return conn.execute(
            f"SELECT * FROM expenses WHERE {clauses}", tuple(filters.values())
        ).fetchall()
    finally:
        conn.close()


def _valid(**overrides):
    data = {
        "amount": "50.0",
        "category": "Food",
        "date": "2026-03-20",
        "description": "Lunch",
    }
    data.update(overrides)
    return data


def _is_login_redirect(response):
    return response.status_code == 302 and "/login" in response.headers["Location"]


def _is_profile_redirect(response):
    loc = response.headers.get("Location", "")
    return response.status_code == 302 and loc.split("?")[0].endswith("/profile")


# ---------------------------------------------------------------------------
# insert_expense unit tests
# ---------------------------------------------------------------------------
class TestInsertExpense:
    def test_insert_expense_valid_inserts_row(self, client):
        uid = _demo_user_id()
        before = _count_expenses()
        queries.insert_expense(uid, 50.0, "Food", "2026-03-20", "Lunch")
        assert _count_expenses() == before + 1, "Expected one new row"
        rows = _find_expenses(
            user_id=uid, category="Food", date="2026-03-20", description="Lunch"
        )
        assert len(rows) == 1, "New row should be retrievable"
        assert rows[0]["amount"] == pytest.approx(50.0)

    def test_insert_expense_none_description_stores_null(self, client):
        uid = _demo_user_id()
        queries.insert_expense(uid, 12.5, "Bills", "2026-03-21", None)
        rows = _find_expenses(user_id=uid, date="2026-03-21", category="Bills")
        assert len(rows) == 1
        assert rows[0]["description"] is None, "description should be NULL"


# ---------------------------------------------------------------------------
# Auth guards
# ---------------------------------------------------------------------------
class TestAuthGuard:
    def test_get_add_expense_unauthenticated_redirects_to_login(self, client):
        response = client.get(ADD_URL)
        assert _is_login_redirect(response), "GET should redirect to /login"

    def test_post_add_expense_unauthenticated_redirects_to_login(self, client):
        response = client.post(ADD_URL, data=_valid())
        assert _is_login_redirect(response), "POST should redirect to /login"

    def test_post_unauthenticated_inserts_no_row(self, client):
        before = _count_expenses()
        client.post(ADD_URL, data=_valid(description="ghost-unauth"))
        assert _count_expenses() == before
        assert _find_expenses(description="ghost-unauth") == []


# ---------------------------------------------------------------------------
# GET form rendering
# ---------------------------------------------------------------------------
class TestGetForm:
    def test_get_authenticated_returns_200(self, logged_in):
        assert logged_in.get(ADD_URL).status_code == 200

    def test_get_form_has_post_method(self, logged_in):
        html = logged_in.get(ADD_URL).get_data(as_text=True)
        form_tags = re.findall(r"<form\b[^>]*>", html, flags=re.I)
        assert any(
            re.search(r'method\s*=\s*["\']post["\']', t, re.I) for t in form_tags
        ), "Expected a <form> with method POST"

    def test_get_form_posts_to_add_expense(self, logged_in):
        html = logged_in.get(ADD_URL).get_data(as_text=True)
        assert re.search(
            r'<form\b[^>]*action\s*=\s*["\'][^"\']*/expenses/add["\']', html, re.I
        ), "Form action should target /expenses/add"

    def test_get_form_has_expected_fields(self, logged_in):
        html = logged_in.get(ADD_URL).get_data(as_text=True)
        for name in ("amount", "category", "date", "description"):
            assert re.search(
                rf'name\s*=\s*["\']{name}["\']', html
            ), f"Missing field {name}"

    def test_get_form_category_select_has_exactly_seven_options(self, logged_in):
        html = logged_in.get(ADD_URL).get_data(as_text=True)
        select = re.search(
            r"<select\b[^>]*name\s*=\s*[\"']category[\"'][^>]*>(.*?)</select>",
            html,
            re.S | re.I,
        )
        assert select, "Expected a category <select>"
        # Only submittable options count; a disabled placeholder is allowed.
        options = re.findall(
            r"<option\b(?![^>]*\bdisabled\b)[^>]*>(.*?)</option>", select.group(1), re.S
        )
        labels = [o.strip() for o in options]
        assert labels == CATEGORIES, f"Unexpected options: {labels}"

    def test_get_form_amount_input_attributes(self, logged_in):
        html = logged_in.get(ADD_URL).get_data(as_text=True)
        tag = re.search(r"<input\b[^>]*name\s*=\s*[\"']amount[\"'][^>]*>", html, re.I)
        assert tag, "Expected amount input"
        t = tag.group(0)
        assert "number" in t
        assert "0.01" in t
        assert "required" in t

    def test_get_form_description_has_max_length_200(self, logged_in):
        html = logged_in.get(ADD_URL).get_data(as_text=True)
        tag = re.search(
            r"<input\b[^>]*name\s*=\s*[\"']description[\"'][^>]*>", html, re.I
        )
        assert tag, "Expected description input"
        assert re.search(r'maxlength\s*=\s*["\']?200', tag.group(0), re.I)

    def test_get_form_date_defaults_to_today(self, logged_in):
        html = logged_in.get(ADD_URL).get_data(as_text=True)
        tag = re.search(r"<input\b[^>]*name\s*=\s*[\"']date[\"'][^>]*>", html, re.I)
        assert tag, "Expected date input"
        assert "date" in tag.group(0)
        assert date.today().isoformat() in tag.group(0), "Date should default to today"

    def test_get_form_has_save_button_and_cancel_link(self, logged_in):
        html = logged_in.get(ADD_URL).get_data(as_text=True)
        assert "Save Expense" in html
        assert re.search(r'<a\b[^>]*href\s*=\s*["\'][^"\']*/profile["\']', html)

    def test_get_form_has_no_wrong_currency_symbols(self, logged_in):
        html = logged_in.get(ADD_URL).get_data(as_text=True)
        assert "£" not in html
        assert "$" not in html


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------
def test_categories_constant_has_seven_expected_values():
    assert list(queries.CATEGORIES) == CATEGORIES


def test_seeded_categories_match_queries_categories(client):
    conn = db.get_db()
    try:
        rows = conn.execute("SELECT DISTINCT category FROM expenses").fetchall()
    finally:
        conn.close()
    assert {r["category"] for r in rows} == set(queries.CATEGORIES)


# ---------------------------------------------------------------------------
# POST happy paths
# ---------------------------------------------------------------------------
class TestPostSuccess:
    def test_post_amount_at_maximum_is_accepted(self, logged_in):
        response = logged_in.post(ADD_URL, data=_valid(amount="10000000"))
        assert _is_profile_redirect(response)

    def test_post_valid_redirects_to_profile(self, logged_in):
        response = logged_in.post(ADD_URL, data=_valid())
        assert _is_profile_redirect(response), response.headers.get("Location")

    def test_post_valid_inserts_row_for_logged_in_user(self, logged_in):
        uid = _demo_user_id()
        before = len(_find_expenses(user_id=uid))
        logged_in.post(ADD_URL, data=_valid(description="Unique lunch 7"))
        rows = _find_expenses(user_id=uid, description="Unique lunch 7")
        assert len(rows) == 1
        row = rows[0]
        assert row["amount"] == pytest.approx(50.0)
        assert row["category"] == "Food"
        assert row["date"] == "2026-03-20"
        assert len(_find_expenses(user_id=uid)) == before + 1

    def test_post_valid_does_not_attach_to_other_user(self, logged_in):
        other_id = db.create_user("Other", "other@example.com", "pw12345")
        logged_in.post(ADD_URL, data=_valid(description="mine only"))
        assert _find_expenses(user_id=other_id) == []

    def test_post_valid_follow_redirect_shows_expense_on_profile(self, logged_in):
        response = logged_in.post(
            ADD_URL,
            data=_valid(amount="1234.56", description="Zebra purchase"),
            follow_redirects=True,
        )
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "Zebra purchase" in body, "New expense should appear on profile"
        assert "₹" in body, "Currency must be rupee"
        assert "£" not in body

    @pytest.mark.parametrize("category", CATEGORIES)
    def test_post_each_valid_category_accepted(self, logged_in, category):
        response = logged_in.post(
            ADD_URL, data=_valid(category=category, description=f"cat-{category}")
        )
        assert _is_profile_redirect(response)
        assert len(_find_expenses(description=f"cat-{category}")) == 1

    @pytest.mark.parametrize("amount", ["0.01", "1", "99999.99", "10.5"])
    def test_post_valid_amounts_accepted(self, logged_in, amount):
        response = logged_in.post(ADD_URL, data=_valid(amount=amount, description="amt"))
        assert _is_profile_redirect(response)
        rows = _find_expenses(description="amt")
        assert len(rows) == 1
        assert rows[0]["amount"] == pytest.approx(float(amount))

    def test_post_no_description_stores_null(self, logged_in):
        data = _valid()
        del data["description"]
        data["date"] = "2026-04-01"
        data["category"] = "Health"
        response = logged_in.post(ADD_URL, data=data)
        assert _is_profile_redirect(response)
        rows = _find_expenses(
            user_id=_demo_user_id(), date="2026-04-01", category="Health"
        )
        assert len(rows) == 1
        assert rows[0]["description"] is None

    @pytest.mark.parametrize("blank", ["", "   ", "\t "])
    def test_post_blank_description_stores_null(self, logged_in, blank):
        response = logged_in.post(
            ADD_URL, data=_valid(description=blank, date="2026-04-02", category="Other")
        )
        assert _is_profile_redirect(response)
        rows = _find_expenses(date="2026-04-02", category="Other")
        assert len(rows) == 1
        assert rows[0]["description"] is None

    def test_post_description_is_stripped(self, logged_in):
        logged_in.post(ADD_URL, data=_valid(description="   padded   "))
        assert len(_find_expenses(description="padded")) == 1

    def test_post_description_exactly_200_chars_accepted(self, logged_in):
        desc = "a" * 200
        response = logged_in.post(ADD_URL, data=_valid(description=desc))
        assert _is_profile_redirect(response)
        assert len(_find_expenses(description=desc)) == 1

    def test_post_sql_injection_description_stored_literally(self, logged_in):
        payload = "x'); DROP TABLE expenses;--"
        response = logged_in.post(ADD_URL, data=_valid(description=payload))
        assert _is_profile_redirect(response)
        assert len(_find_expenses(description=payload)) == 1
        assert _count_expenses() > 0, "expenses table must still exist"


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
            {"amount": "-0.01"},
            {"amount": "abc"},
            {"amount": "12abc"},
            {"amount": "nan"},
            {"amount": "inf"},
            {"amount": "-inf"},
            {"amount": "1e308"},
            {"amount": "10000000.01"},
            {"category": ""},
            {"category": "Groceries"},
            {"category": "food"},
            {"category": "'; DROP TABLE expenses;--"},
            {"date": ""},
            {"date": "not-a-date"},
            {"date": "2026-13-01"},
            {"date": "2026-02-30"},
            {"date": "20/03/2026"},
            {"description": "d" * 201},
            {"description": "d" * 1000},
        ],
        ids=lambda o: "-".join(f"{k}={str(v)[:12]}" for k, v in o.items()),
    )
    def test_post_invalid_rerenders_form_with_error_and_no_insert(
        self, logged_in, overrides
    ):
        before = _count_expenses()
        response = logged_in.post(ADD_URL, data=_valid(**overrides))
        assert response.status_code == 200, "Invalid input must re-render form"
        html = response.get_data(as_text=True)
        assert "<form" in html, "Form should be re-rendered"
        assert re.search(r"error|invalid|required|must|please", html, re.I), (
            "Expected an error message"
        )
        assert _count_expenses() == before, "No row should be inserted"

    def test_post_missing_amount_field_entirely(self, logged_in):
        data = _valid()
        del data["amount"]
        before = _count_expenses()
        response = logged_in.post(ADD_URL, data=data)
        assert response.status_code == 200
        assert _count_expenses() == before

    def test_post_missing_category_field_entirely(self, logged_in):
        data = _valid()
        del data["category"]
        before = _count_expenses()
        response = logged_in.post(ADD_URL, data=data)
        assert response.status_code == 200
        assert _count_expenses() == before

    def test_post_missing_date_field_entirely(self, logged_in):
        data = _valid()
        del data["date"]
        before = _count_expenses()
        response = logged_in.post(ADD_URL, data=data)
        assert response.status_code == 200
        assert _count_expenses() == before

    def test_post_empty_body_rerenders_form(self, logged_in):
        before = _count_expenses()
        response = logged_in.post(ADD_URL, data={})
        assert response.status_code == 200
        assert _count_expenses() == before


# ---------------------------------------------------------------------------
# Re-population after error
# ---------------------------------------------------------------------------
class TestRepopulation:
    def test_error_preserves_description_and_date(self, logged_in):
        response = logged_in.post(
            ADD_URL,
            data=_valid(amount="0", description="Keep me please", date="2026-05-05"),
        )
        html = response.get_data(as_text=True)
        assert response.status_code == 200
        assert "Keep me please" in html
        assert "2026-05-05" in html

    def test_error_preserves_amount(self, logged_in):
        response = logged_in.post(
            ADD_URL, data=_valid(category="Nope", amount="77.25")
        )
        html = response.get_data(as_text=True)
        assert "77.25" in html, "Amount should be re-populated"

    def test_error_preserves_selected_category(self, logged_in):
        response = logged_in.post(
            ADD_URL, data=_valid(amount="", category="Transport")
        )
        html = response.get_data(as_text=True)
        assert re.search(
            r"<option\b[^>]*selected[^>]*>\s*Transport\s*</option>"
            r"|<option\b[^>]*value\s*=\s*[\"']Transport[\"'][^>]*selected",
            html,
            re.I,
        ), "Transport should remain selected"

    def test_error_preserves_invalid_date_not_reset_to_today_crash(self, logged_in):
        response = logged_in.post(ADD_URL, data=_valid(date="garbage"))
        assert response.status_code == 200, "Must not crash on bad date"


# ---------------------------------------------------------------------------
# Navigation / UI
# ---------------------------------------------------------------------------
class TestNavigation:
    def test_profile_has_add_expense_link(self, logged_in):
        html = logged_in.get("/profile").get_data(as_text=True)
        assert re.search(
            r'<a\b[^>]*href\s*=\s*["\'][^"\']*/expenses/add["\'][^>]*>[^<]*Add Expense',
            html,
            re.S,
        ), "Profile should link to /expenses/add with 'Add Expense'"

    def test_navbar_shows_add_expense_when_logged_in(self, logged_in):
        html = logged_in.get("/profile").get_data(as_text=True)
        nav = re.search(r"<nav\b.*?</nav>", html, re.S | re.I)
        assert nav, "Expected a <nav>"
        assert "Add Expense" in nav.group(0)
        assert "/expenses/add" in nav.group(0)

    @pytest.mark.parametrize("path", ["/", "/login", "/register"])
    def test_navbar_hides_add_expense_when_logged_out(self, client, path):
        html = client.get(path).get_data(as_text=True)
        assert "Add Expense" not in html
        assert "/expenses/add" not in html

    def test_navbar_hides_add_expense_after_logout(self, logged_in):
        logged_in.get("/logout")
        html = logged_in.get("/login").get_data(as_text=True)
        assert "Add Expense" not in html

    def test_add_expense_page_extends_base_layout(self, logged_in):
        html = logged_in.get(ADD_URL).get_data(as_text=True)
        assert "<nav" in html.lower(), "Page should include base navbar"
