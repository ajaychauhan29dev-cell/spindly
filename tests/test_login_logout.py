import pytest

from database import db

EMAIL = "test@example.com"
PASSWORD = "secret123"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    from app import app

    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def user_id(client):
    return db.create_user("Test User", EMAIL, PASSWORD)


def _login(client, email=EMAIL, password=PASSWORD, **kwargs):
    return client.post(
        "/login", data={"email": email, "password": password}, **kwargs
    )


def test_get_user_by_email_found(user_id):
    user = db.get_user_by_email(EMAIL)
    assert user["id"] == user_id
    assert user["email"] == EMAIL


def test_get_user_by_email_missing(client):
    assert db.get_user_by_email("nobody@example.com") is None


def test_get_login_renders_form(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    assert b'name="email"' in resp.data
    assert b'name="password"' in resp.data


def test_valid_login_sets_session_and_redirects(client, user_id):
    resp = _login(client)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")
    with client.session_transaction() as sess:
        assert sess["user_id"] == user_id


def test_login_normalizes_email(client, user_id):
    resp = _login(client, email="  TEST@Example.com ")
    assert resp.status_code == 302
    with client.session_transaction() as sess:
        assert sess["user_id"] == user_id


@pytest.mark.parametrize(
    "email, password",
    [
        (EMAIL, "wrong-password"),
        ("unknown@example.com", PASSWORD),
        ("", PASSWORD),
        (EMAIL, ""),
    ],
)
def test_invalid_login_shows_generic_error(client, user_id, email, password):
    resp = _login(client, email=email, password=password)
    assert resp.status_code == 200
    assert b"Invalid email or password." in resp.data
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_failed_login_refills_email(client, user_id):
    resp = _login(client, password="wrong-password")
    assert EMAIL.encode() in resp.data


def test_logout_clears_session(client, user_id):
    _login(client)
    resp = client.get("/logout")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")
    assert b"coming in Step 3" not in resp.data
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_logout_as_guest_redirects(client):
    resp = client.get("/logout")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")


@pytest.mark.parametrize("path", ["/login", "/register"])
def test_logged_in_user_redirected_from_auth_pages(client, user_id, path):
    _login(client)
    for resp in (client.get(path), client.post(path, data={})):
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/")


def test_nav_shows_sign_out_only_when_logged_in(client, user_id):
    assert b"Sign out" not in client.get("/").data
    _login(client)
    page = client.get("/").data
    assert b"Sign out" in page
    assert b"Sign in" not in page
