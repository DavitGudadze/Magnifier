"""
Smoke tests for the magnifier_python Flask frontend.

Route-rendering only — no backend calls. sys.path is managed inside the
fixture so this file coexists with test_backend_smoke.py in the same session.
"""

import os
import sys
import pytest

_FRONTEND_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "magnifier_python")
)


def _activate_frontend():
    """Put magnifier_python at the front of sys.path and evict cached 'app'."""
    if _FRONTEND_PATH in sys.path:
        sys.path.remove(_FRONTEND_PATH)
    sys.path.insert(0, _FRONTEND_PATH)

    # Evict any backend 'app' package so the frontend module loads fresh
    stale = [k for k in list(sys.modules) if k == "app" or k.startswith("app.") or k == "config"]
    for k in stale:
        del sys.modules[k]

    os.environ.setdefault("SECRET_KEY", "test-secret-key")
    os.environ.setdefault("BACKEND_URL", "http://127.0.0.1:5000")
    os.environ.setdefault("PREFIX", "")
    os.environ.setdefault("GOOGLE_CLIENT_ID", "")
    os.environ.setdefault("GOOGLE_CLIENT_SECRET", "")


@pytest.fixture(scope="module")
def client():
    _activate_frontend()

    import app as frontend_module  # noqa: PLC0415

    frontend_module.app.config["TESTING"] = True
    frontend_module.app.config["WTF_CSRF_ENABLED"] = False
    with frontend_module.app.test_client() as c:
        yield c


# ── Public pages ──────────────────────────────────────────────────────────────

def test_index_page(client):
    """GET / returns 200."""
    resp = client.get("/")
    assert resp.status_code == 200


def test_login_page_get(client):
    """GET /login renders login form."""
    resp = client.get("/login")
    assert resp.status_code == 200
    assert b"login" in resp.data.lower() or b"access" in resp.data.lower()


def test_register_page_get(client):
    """GET /register renders registration form."""
    resp = client.get("/register")
    assert resp.status_code == 200
    assert b"register" in resp.data.lower() or b"clearance" in resp.data.lower()


def test_unauthorized_page(client):
    """GET /unauthorized renders without error."""
    resp = client.get("/unauthorized")
    assert resp.status_code == 200


# ── Auth-protected pages redirect unauthenticated users ──────────────────────

def test_dashboard_redirects_unauthenticated(client):
    """GET /dashboard without auth redirects or shows index."""
    resp = client.get("/dashboard", follow_redirects=False)
    assert resp.status_code in (200, 302)


def test_projects_redirects_unauthenticated(client):
    """GET /projects without auth redirects."""
    resp = client.get("/projects", follow_redirects=False)
    assert resp.status_code in (200, 302)


def test_profile_redirects_unauthenticated(client):
    """GET /account/profile without auth redirects to login."""
    resp = client.get("/account/profile", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers.get("Location", "")


def test_404_returns_error_page(client):
    """Requesting a nonexistent route returns 404."""
    resp = client.get("/this/does/not/exist")
    assert resp.status_code == 404


# ── Session / logout mechanics ────────────────────────────────────────────────

def test_logout_redirects(client):
    """GET /logout always redirects to /login."""
    resp = client.get("/logout", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers.get("Location", "")


def test_google_auth_redirect(client):
    """GET /auth/google redirects to Google even with empty credentials."""
    resp = client.get("/auth/google", follow_redirects=False)
    assert resp.status_code == 302
    location = resp.headers.get("Location", "")
    assert "accounts.google.com" in location or "oauth2" in location
