"""Tests for Step 6: date-range filter on GET /profile (spec 06-date-filter-profile)."""

import html as html_lib
import re
from datetime import date
from urllib.parse import parse_qs, urlparse

import pytest

from database import db
from database import queries

EMAIL = "filter@example.com"
PASSWORD = "secret123"
ERROR_MSG = "Start date must be before end date."

# Fixed-date rows: (amount, category, date, description)
ROWS = [
    (100.00, "Food", "2020-01-10", "Lunch"),
    (200.00, "Bills", "2020-01-15", "Electricity"),
    (50.00, "Food", "2020-01-20", "Dinner"),
    (400.00, "Shopping", "2020-02-01", "Jacket"),
]


def _insert_expenses(user_id, rows):
    conn = db.get_db()
    try:
        for amount, category, day, description in rows:
            conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, amount, category, day, description),
            )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def user_id(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "filter.db"))
    db.init_db()
    uid = db.create_user("Filter User", EMAIL, PASSWORD)
    _insert_expenses(uid, ROWS)
    return uid


@pytest.fixture
def empty_user_id(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "filter_empty.db"))
    db.init_db()
    return db.create_user("Empty Filter", "emptyf@example.com", PASSWORD)


@pytest.fixture
def client(user_id):
    from app import app

    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def logged_in(client):
    client.post("/login", data={"email": EMAIL, "password": PASSWORD})
    return client


@pytest.fixture
def empty_client(empty_user_id):
    from app import app

    app.config["TESTING"] = True
    c = app.test_client()
    c.post("/login", data={"email": "emptyf@example.com", "password": PASSWORD})
    return c


# ---------- helpers ----------

def _page(client, **params):
    response = client.get("/profile", query_string=params)
    assert response.status_code == 200, "Expected profile page to render"
    return response.get_data(as_text=True)


def _txn_count(page):
    return page.count('<td class="txn-amount">')


def _category_count(page):
    return page.count('class="category-row"')


def _stat_values(page):
    return [
        v.strip()
        for v in re.findall(r'<span class="stat-value">(.*?)</span>', page, re.S)
    ]


def _anchor(page, label):
    match = re.search(r"<a\b[^>]*>\s*" + re.escape(label) + r"\s*</a>", page)
    assert match, f"Expected a link labelled {label!r}"
    return match.group(0)


def _href(anchor):
    return html_lib.unescape(re.search(r'href="([^"]*)"', anchor).group(1))


# ---------- unfiltered ----------

class TestUnfiltered:
    def test_no_params_shows_all_expenses(self, logged_in):
        page = _page(logged_in)
        assert _txn_count(page) == 4
        assert _category_count(page) == 3
        stats = _stat_values(page)
        assert "750.00" in stats[0]
        assert stats[1] == "4"

    def test_no_params_matches_all_time_href(self, logged_in):
        a = _page(logged_in)
        b = _page(logged_in, date_from="", date_to="")
        assert _txn_count(a) == _txn_count(b) == 4


# ---------- custom range ----------

class TestCustomRange:
    def test_range_filters_all_three_sections(self, logged_in):
        page = _page(logged_in, date_from="2020-01-01", date_to="2020-01-31")
        assert _txn_count(page) == 3
        assert "Jacket" not in page
        assert _category_count(page) == 2  # Food, Bills
        stats = _stat_values(page)
        assert "350.00" in stats[0]
        assert stats[1] == "3"
        assert stats[2] == "Bills"

    def test_bounds_are_inclusive(self, logged_in):
        page = _page(logged_in, date_from="2020-01-10", date_to="2020-01-20")
        assert _txn_count(page) == 3
        assert "Lunch" in page and "Dinner" in page and "Electricity" in page

    def test_single_day_range_works(self, logged_in):
        page = _page(logged_in, date_from="2020-02-01", date_to="2020-02-01")
        assert _txn_count(page) == 1
        assert "Jacket" in page
        assert _stat_values(page)[1] == "1"
        assert _stat_values(page)[2] == "Shopping"

    def test_filter_does_not_include_other_users_expenses(self, logged_in, user_id):
        other = db.create_user("Other", "other@example.com", PASSWORD)
        _insert_expenses(other, [(999.00, "Travel", "2020-01-12", "Flight")])
        page = _page(logged_in, date_from="2020-01-01", date_to="2020-01-31")
        assert "Flight" not in page
        assert _txn_count(page) == 3

    def test_custom_range_values_echoed_in_inputs(self, logged_in):
        page = _page(logged_in, date_from="2020-01-01", date_to="2020-01-31")
        assert 'value="2020-01-01"' in page
        assert 'value="2020-01-31"' in page
        assert page.count('type="date"') == 2

    def test_percentages_recalculated_for_range(self, logged_in):
        page = _page(logged_in, date_from="2020-01-01", date_to="2020-01-31")
        pcts = [int(p) for p in re.findall(r'<progress[^>]*value="(\d+)"', page)]
        assert sum(pcts) == 100
        assert len(pcts) == 2


# ---------- invalid input ----------

class TestInvalidInput:
    def test_from_after_to_flashes_error_and_is_unfiltered(self, logged_in):
        page = _page(logged_in, date_from="2020-02-01", date_to="2020-01-01")
        assert ERROR_MSG in page
        assert _txn_count(page) == 4
        assert _stat_values(page)[1] == "4"

    def test_error_flash_is_not_repeated_on_next_request(self, logged_in):
        first = _page(logged_in, date_from="2020-02-01", date_to="2020-01-01")
        assert ERROR_MSG in first
        second = _page(logged_in)
        assert ERROR_MSG not in second, "Flash message must be shown only once"

    def test_error_not_shown_for_valid_range(self, logged_in):
        page = _page(logged_in, date_from="2020-01-01", date_to="2020-01-31")
        assert ERROR_MSG not in page

    def test_error_not_shown_when_from_equals_to(self, logged_in):
        page = _page(logged_in, date_from="2020-01-10", date_to="2020-01-10")
        assert ERROR_MSG not in page
        assert _txn_count(page) == 1

    @pytest.mark.parametrize(
        "params",
        [
            {"date_from": "not-a-date", "date_to": "2020-01-31"},
            {"date_from": "2020-01-01", "date_to": "not-a-date"},
            {"date_from": "not-a-date", "date_to": "also-bad"},
            {"date_from": "2020-13-45", "date_to": "2020-01-31"},
            {"date_from": "01/01/2020", "date_to": "31/01/2020"},
            {"date_from": "2020-02-30", "date_to": "2020-03-01"},
            {"date_from": "' OR 1=1 --", "date_to": "2020-01-31"},
            {"date_from": "2020-01-01'; DROP TABLE expenses;--", "date_to": "2020-01-31"},
            {"date_from": "x" * 5000, "date_to": "2020-01-31"},
        ],
    )
    def test_malformed_date_falls_back_silently(self, logged_in, params):
        response = logged_in.get("/profile", query_string=params)
        assert response.status_code == 200, "Malformed date must not crash"
        page = response.get_data(as_text=True)
        assert _txn_count(page) == 4
        assert ERROR_MSG not in page

    def test_sql_injection_attempt_leaves_table_intact(self, logged_in):
        logged_in.get(
            "/profile",
            query_string={"date_from": "2020-01-01'; DROP TABLE expenses;--",
                          "date_to": "2020-01-31"},
        )
        assert _txn_count(_page(logged_in)) == 4

    @pytest.mark.parametrize(
        "params",
        [
            {"date_from": "2020-01-01"},
            {"date_to": "2020-01-31"},
            {"date_from": "2020-01-01", "date_to": ""},
            {"date_from": "", "date_to": "2020-01-31"},
        ],
    )
    def test_only_one_param_falls_back_to_unfiltered(self, logged_in, params):
        page = _page(logged_in, **params)
        assert _txn_count(page) == 4
        assert _stat_values(page)[1] == "4"
        assert ERROR_MSG not in page


# ---------- presets and active state ----------

class TestPresets:
    LABELS = ["This Month", "Last 3 Months", "Last 6 Months", "All Time"]

    @pytest.mark.parametrize("label", LABELS)
    def test_preset_link_present(self, logged_in, label):
        page = _page(logged_in)
        assert label in page
        assert _anchor(page, label)

    def test_all_time_href_is_exactly_profile(self, logged_in):
        page = _page(logged_in)
        assert _href(_anchor(page, "All Time")) == "/profile"

    def test_this_month_href_spans_current_month(self, logged_in):
        today = date.today()
        href = _href(_anchor(_page(logged_in), "This Month"))
        qs = parse_qs(urlparse(href).query)
        assert urlparse(href).path == "/profile"
        assert qs["date_from"] == [today.replace(day=1).isoformat()]
        assert qs["date_to"][0] >= today.isoformat() or qs["date_to"][0].startswith(
            today.strftime("%Y-%m")
        )

    @pytest.mark.parametrize("label", ["Last 3 Months", "Last 6 Months"])
    def test_multi_month_preset_ends_today(self, logged_in, label):
        href = _href(_anchor(_page(logged_in), label))
        qs = parse_qs(urlparse(href).query)
        assert qs["date_to"] == [date.today().isoformat()]
        assert qs["date_from"][0] < date.today().isoformat()

    def test_six_month_window_starts_before_three_month_window(self, logged_in):
        page = _page(logged_in)
        three = parse_qs(urlparse(_href(_anchor(page, "Last 3 Months"))).query)
        six = parse_qs(urlparse(_href(_anchor(page, "Last 6 Months"))).query)
        assert six["date_from"][0] < three["date_from"][0]

    @pytest.mark.parametrize("label", ["This Month", "Last 3 Months", "Last 6 Months"])
    def test_following_preset_link_returns_200(self, logged_in, label):
        href = _href(_anchor(_page(logged_in), label))
        assert logged_in.get(href).status_code == 200

    def test_old_fixed_data_excluded_by_this_month(self, logged_in):
        href = _href(_anchor(_page(logged_in), "This Month"))
        page = logged_in.get(href).get_data(as_text=True)
        assert _txn_count(page) == 0
        assert "₹0.00" in page

    def test_current_month_expense_included_by_this_month(self, logged_in, user_id):
        _insert_expenses(user_id, [(77.00, "Health", date.today().isoformat(), "Checkup")])
        href = _href(_anchor(_page(logged_in), "This Month"))
        page = logged_in.get(href).get_data(as_text=True)
        assert "Checkup" in page
        assert "Lunch" not in page

    @pytest.mark.parametrize("label", ["This Month", "Last 3 Months", "Last 6 Months"])
    def test_active_class_on_selected_preset_only(self, logged_in, label):
        href = _href(_anchor(_page(logged_in), label))
        page = logged_in.get(href).get_data(as_text=True)
        assert "active" in _anchor(page, label), f"{label} should be active"
        for other in self.LABELS:
            if other != label:
                assert "active" not in _anchor(page, other), (
                    f"{other} should not be active when {label} selected"
                )

    def test_active_class_on_all_time_without_params(self, logged_in):
        page = _page(logged_in)
        assert "active" in _anchor(page, "All Time")
        for other in self.LABELS[:3]:
            assert "active" not in _anchor(page, other)

    def test_no_preset_active_for_custom_range(self, logged_in):
        page = _page(logged_in, date_from="2020-01-01", date_to="2020-01-31")
        for label in self.LABELS[:3]:
            assert "active" not in _anchor(page, label)

    def test_apply_button_present(self, logged_in):
        assert "Apply" in _page(logged_in)


# ---------- currency and empty ranges ----------

class TestCurrencyAndEmpty:
    def test_rupee_symbol_with_filter(self, logged_in):
        page = _page(logged_in, date_from="2020-01-01", date_to="2020-01-31")
        assert "₹" in page
        assert "₹350.00" in page
        assert "$" not in "".join(_stat_values(page))

    def test_empty_range_shows_zero_state(self, logged_in):
        page = _page(logged_in, date_from="1999-01-01", date_to="1999-12-31")
        stats = _stat_values(page)
        assert "₹0.00" in stats[0]
        assert stats[1] == "0"
        assert _txn_count(page) == 0
        assert _category_count(page) == 0

    def test_user_without_expenses_filtered_view_ok(self, empty_client):
        response = empty_client.get(
            "/profile",
            query_string={"date_from": "2020-01-01", "date_to": "2020-12-31"},
        )
        assert response.status_code == 200
        page = response.get_data(as_text=True)
        assert "₹0.00" in page
        assert _txn_count(page) == 0
        assert _category_count(page) == 0


# ---------- auth guard ----------

class TestAuthGuard:
    def test_unauthenticated_redirects_to_login(self, client):
        response = client.get("/profile")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

    def test_unauthenticated_with_filter_redirects_to_login(self, client):
        response = client.get(
            "/profile",
            query_string={"date_from": "2020-01-01", "date_to": "2020-01-31"},
        )
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")


# ---------- query helpers ----------

class TestQueryHelpers:
    def test_summary_stats_with_range(self, user_id):
        stats = queries.get_summary_stats(
            user_id, date_from="2020-01-01", date_to="2020-01-31"
        )
        assert stats["total_spent"] == 350.00
        assert stats["transaction_count"] == 3
        assert stats["top_category"] == "Bills"

    def test_summary_stats_inclusive_bounds(self, user_id):
        stats = queries.get_summary_stats(
            user_id, date_from="2020-01-15", date_to="2020-02-01"
        )
        assert stats["transaction_count"] == 3
        assert stats["total_spent"] == 650.00

    def test_summary_stats_no_params_unfiltered(self, user_id):
        stats = queries.get_summary_stats(user_id)
        assert stats["transaction_count"] == 4
        assert stats["total_spent"] == 750.00

    def test_summary_stats_empty_range(self, user_id):
        stats = queries.get_summary_stats(
            user_id, date_from="1999-01-01", date_to="1999-01-02"
        )
        assert stats["total_spent"] == 0
        assert stats["transaction_count"] == 0

    def test_transactions_with_range(self, user_id):
        txns = queries.get_recent_transactions(
            user_id, date_from="2020-01-01", date_to="2020-01-31"
        )
        assert [t["description"] for t in txns] == ["Dinner", "Electricity", "Lunch"]

    def test_transactions_no_params_unfiltered(self, user_id):
        txns = queries.get_recent_transactions(user_id)
        assert len(txns) == 4
        assert txns[0]["description"] == "Jacket"

    def test_transactions_limit_still_applies_with_range(self, user_id):
        txns = queries.get_recent_transactions(
            user_id, limit=2, date_from="2020-01-01", date_to="2020-01-31"
        )
        assert [t["description"] for t in txns] == ["Dinner", "Electricity"]

    def test_transactions_empty_range(self, user_id):
        assert queries.get_recent_transactions(
            user_id, date_from="1999-01-01", date_to="1999-01-02"
        ) == []

    def test_breakdown_with_range(self, user_id):
        cats = queries.get_category_breakdown(
            user_id, date_from="2020-01-01", date_to="2020-01-31"
        )
        assert [c["name"] for c in cats] == ["Bills", "Food"]
        assert [c["amount"] for c in cats] == [200.00, 150.00]
        assert sum(c["pct"] for c in cats) == 100

    def test_breakdown_no_params_unfiltered(self, user_id):
        cats = queries.get_category_breakdown(user_id)
        assert {c["name"] for c in cats} == {"Food", "Bills", "Shopping"}
        assert sum(c["pct"] for c in cats) == 100

    def test_breakdown_empty_range(self, user_id):
        assert queries.get_category_breakdown(
            user_id, date_from="1999-01-01", date_to="1999-01-02"
        ) == []


# ---------- date normalisation and helpers ----------

class TestDateNormalisation:
    def test_unpadded_dates_are_normalised(self, logged_in):
        # 2020-1-1..2020-1-31 must behave exactly like the zero-padded range.
        page = _page(logged_in, date_from="2020-1-1", date_to="2020-1-31")
        assert _txn_count(page) == 3
        assert "350.00" in _stat_values(page)[0]

    def test_unpadded_reversed_range_flashes_error(self, logged_in):
        # As raw strings "2020-1-5" > "2020-01-20" would wrongly pass; normalised it is reversed.
        page = _page(logged_in, date_from="2020-1-25", date_to="2020-01-20")
        assert ERROR_MSG in page
        assert _txn_count(page) == 4

    def test_months_ago_clamps_to_month_end(self):
        from app import _months_ago

        assert _months_ago(date(2026, 3, 31), 1) == date(2026, 2, 28)
        assert _months_ago(date(2024, 3, 31), 1) == date(2024, 2, 29)
        assert _months_ago(date(2026, 8, 31), 6) == date(2026, 2, 28)

    def test_months_ago_crosses_year_boundary(self):
        from app import _months_ago

        assert _months_ago(date(2026, 1, 15), 3) == date(2025, 10, 15)
        assert _months_ago(date(2026, 1, 31), 12) == date(2025, 1, 31)

    def test_recent_transactions_dates_are_keyword_only(self, user_id):
        with pytest.raises(TypeError):
            queries.get_recent_transactions(user_id, 10, "2020-01-01", "2020-01-31")
