import re
from pathlib import Path

import pytest

from database import db

EMAIL = "test@example.com"
PASSWORD = "secret123"
TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "profile.html"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    from app import app

    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def logged_in(client):
    db.create_user("Test User", EMAIL, PASSWORD)
    client.post("/login", data={"email": EMAIL, "password": PASSWORD})
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
    assert "demo@spendly.com" in html
    assert "Member since" in html


def test_profile_shows_stats(logged_in):
    html = logged_in.get("/profile").get_data(as_text=True)
    assert html.count('class="stat-tile"') >= 3


def test_profile_shows_transactions(logged_in):
    html = logged_in.get("/profile").get_data(as_text=True)
    assert html.count('class="txn-amount"') >= 3
    assert "badge-" in html


def test_profile_shows_category_breakdown(logged_in):
    html = logged_in.get("/profile").get_data(as_text=True)
    assert html.count('class="category-row"') >= 3


def test_navbar_shows_username_and_logout(logged_in):
    html = logged_in.get("/profile").get_data(as_text=True)
    assert 'class="nav-user">Test User<' in html
    assert "/logout" in html


def test_template_has_no_hex_colours_or_inline_styles():
    source = TEMPLATE.read_text()
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", source)
    assert "style=" not in source
