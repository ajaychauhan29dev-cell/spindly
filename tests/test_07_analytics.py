"""Tests for Step 7: GET /analytics placeholder page and navbar link."""

import re

import pytest

from database import db

EMAIL = "analytics@example.com"
PASSWORD = "secret123"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "analytics.db"))
    db.init_db()
    db.create_user("Analytics User", EMAIL, PASSWORD)
    from app import app

    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def logged_in(client):
    client.post("/login", data={"email": EMAIL, "password": PASSWORD})
    return client


def _analytics_links(body):
    """Return opening <a ...> tags whose href is /analytics."""
    tags = re.findall(r"<a\b[^>]*>", body, flags=re.I)
    return [t for t in tags if re.search(r'href=["\']/analytics(?:\?[^"\']*)?["\']', t)]


def _has_class(tag, name):
    m = re.search(r'class=["\']([^"\']*)["\']', tag)
    return bool(m) and name in m.group(1).split()


class TestAnalyticsAuthGuard:
    def test_logged_out_redirects_to_login(self, client):
        resp = client.get("/analytics")
        assert resp.status_code == 302, "Expected redirect for anonymous visitor"
        assert "/login" in resp.headers["Location"]

    def test_logged_out_redirect_does_not_render_page(self, client):
        resp = client.get("/analytics")
        assert b"Coming soon" not in resp.data

    def test_logged_out_follow_redirect_shows_login(self, client):
        resp = client.get("/analytics", follow_redirects=True)
        assert resp.status_code == 200
        assert resp.request.path == "/login"


class TestAnalyticsPage:
    def test_logged_in_returns_200(self, logged_in):
        resp = logged_in.get("/analytics")
        assert resp.status_code == 200

    def test_logged_in_shows_coming_soon_heading(self, logged_in):
        body = logged_in.get("/analytics").get_data(as_text=True)
        assert "Coming soon." in body, "Expected 'Coming soon.' heading"
        assert re.search(r"<h[1-6][^>]*>\s*Coming soon\.", body), (
            "Expected 'Coming soon.' inside a heading element"
        )

    def test_page_extends_base_layout(self, logged_in):
        body = logged_in.get("/analytics").get_data(as_text=True)
        assert "<nav" in body.lower(), "Expected base navbar to be rendered"

    def test_session_cleared_redirects_again(self, logged_in):
        with logged_in.session_transaction() as sess:
            sess.clear()
        resp = logged_in.get("/analytics")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


class TestAnalyticsNavLink:
    def test_link_hidden_when_logged_out_on_landing(self, client):
        body = client.get("/").get_data(as_text=True)
        assert _analytics_links(body) == [], "Analytics link must be hidden when logged out"

    @pytest.mark.parametrize("path", ["/login", "/register"])
    def test_link_hidden_on_auth_pages_when_logged_out(self, client, path):
        body = client.get(path).get_data(as_text=True)
        assert _analytics_links(body) == []

    def test_link_visible_on_profile_when_logged_in(self, logged_in):
        body = logged_in.get("/profile").get_data(as_text=True)
        links = _analytics_links(body)
        assert len(links) == 1, "Expected exactly one Analytics nav link"
        assert "Analytics" in body

    def test_link_active_on_analytics_page(self, logged_in):
        body = logged_in.get("/analytics").get_data(as_text=True)
        links = _analytics_links(body)
        assert len(links) == 1, "Expected exactly one Analytics nav link"
        assert _has_class(links[0], "active"), f"Expected class 'active': {links[0]}"
        assert re.search(r'aria-current=["\']page["\']', links[0]), (
            f"Expected aria-current=page: {links[0]}"
        )

    def test_link_not_active_on_profile(self, logged_in):
        body = logged_in.get("/profile").get_data(as_text=True)
        links = _analytics_links(body)
        assert links, "Analytics link should be present on /profile"
        assert not _has_class(links[0], "active")
        assert "aria-current" not in links[0]
