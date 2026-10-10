import re
from datetime import datetime
from pathlib import Path

import pytest

from database import db

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"
NEW_EMAIL = "test@example.com"
NEW_PASSWORD = "secret123"
TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "profile.html"


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


@pytest.fixture
def new_user_client(client):
    db.create_user("Test User", NEW_EMAIL, NEW_PASSWORD)
    client.post("/login", data={"email": NEW_EMAIL, "password": NEW_PASSWORD})
    return client


def test_profile_redirects_when_logged_out(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_profile_ok_when_logged_in(logged_in):
    assert logged_in.get("/profile").status_code == 200


def test_profile_shows_user_card(logged_in):
    html = logged_in.get("/profile").get_data(as_text=True)
    assert "Demo User" in html
    assert DEMO_EMAIL in html
    assert "Member since" in html


def test_profile_shows_stats(logged_in):
    html = logged_in.get("/profile").get_data(as_text=True)
    assert html.count('class="stat-tile"') == 3
    assert "₹366.24" in html
    assert "Bills" in html


def test_profile_shows_transactions_newest_first(logged_in):
    html = logged_in.get("/profile").get_data(as_text=True)
    assert html.count('<td class="txn-amount">') == 8
    assert "badge-" in html
    dates = re.findall(r"<td>(\d{2} \w{3} \d{4})</td>", html)
    assert len(dates) == 8
    parsed = [datetime.strptime(d, "%d %b %Y") for d in dates]
    assert parsed == sorted(parsed, reverse=True)


def test_profile_shows_category_breakdown(logged_in):
    html = logged_in.get("/profile").get_data(as_text=True)
    assert html.count('class="category-row"') == 7
    pcts = [int(p) for p in re.findall(r'<progress[^>]*value="(\d+)"', html)]
    assert sum(pcts) == 100


def test_profile_new_user_sees_empty_state(new_user_client):
    response = new_user_client.get("/profile")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "₹0.00" in html
    assert 'class="category-row"' not in html
    assert 'class="txn-amount"' not in html
    assert "No expenses yet." in html


def test_profile_stale_session_redirects_to_login(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 99999
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_navbar_shows_username_and_logout(logged_in):
    html = logged_in.get("/profile").get_data(as_text=True)
    assert 'class="nav-user">Demo User<' in html
    assert "/logout" in html


def test_template_has_no_hex_colours_or_inline_styles():
    source = TEMPLATE.read_text()
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", source)
    assert "style=" not in source
