"""
Smoke tests for the bioworkflow Flask backend.

Each test gets a fresh in-memory SQLite database.
sys.path is managed inside the fixture so this file can coexist with
test_frontend_smoke.py (which also imports a module called 'app') in the same
pytest session.
"""

import os
import sys
import pytest

_BIOWORKFLOW_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "bioworkflow")
)

STRONG_PW = "StrongPass1!"


def _activate_backend():
    """Put bioworkflow at the front of sys.path and evict any cached 'app'."""
    if _BIOWORKFLOW_PATH in sys.path:
        sys.path.remove(_BIOWORKFLOW_PATH)
    sys.path.insert(0, _BIOWORKFLOW_PATH)

    # Evict any cached frontend 'app' so the backend package is imported fresh
    stale = [k for k in list(sys.modules) if k == "app" or k.startswith("app.") or k == "config"]
    for k in stale:
        del sys.modules[k]

    os.environ.setdefault("FLASK_ENV", "testing")
    os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")


@pytest.fixture
def app():
    """Fresh Flask app with an empty in-memory DB for each test."""
    _activate_backend()

    from app import create_app          # noqa: PLC0415
    from app.models import db as _db   # noqa: PLC0415

    application = create_app("testing")
    with application.app_context():
        _db.create_all()
        yield application
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(app):
    """Test client pre-registered and logged in as 'authuser'."""
    c = app.test_client()
    c.post(
        "/auth/register",
        json={
            "username": "authuser",
            "email": "auth@example.com",
            "password": STRONG_PW,
            "confirm_password": STRONG_PW,
        },
    )
    c.post("/auth/login", json={"username": "authuser", "password": STRONG_PW})
    return c


# ── Health / root ─────────────────────────────────────────────────────────────

def test_health_check(client):
    """GET /health returns 200 and status=healthy."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "healthy"
    assert "service" in data


def test_root_endpoint(client):
    """GET / returns 200 with API info."""
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "endpoints" in data


# ── Auth ──────────────────────────────────────────────────────────────────────

def test_register_empty_body(client):
    """POST /auth/register with empty JSON returns 400."""
    resp = client.post("/auth/register", json={})
    assert resp.status_code == 400


def test_register_missing_password(client):
    """POST /auth/register without password returns 400."""
    resp = client.post(
        "/auth/register",
        json={"username": "testuser", "email": "test@example.com"},
    )
    assert resp.status_code == 400


def test_register_password_too_weak(client):
    """POST /auth/register with a weak password is rejected."""
    resp = client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "weak",
            "confirm_password": "weak",
        },
    )
    assert resp.status_code == 400


def test_register_success(client):
    """Valid registration returns 201 with user info."""
    resp = client.post(
        "/auth/register",
        json={
            "username": "newuser",
            "email": "new@example.com",
            "password": STRONG_PW,
            "confirm_password": STRONG_PW,
        },
    )
    assert resp.status_code == 201, resp.get_json()
    body = resp.get_json()
    assert body["user"]["username"] == "newuser"


def test_login_success(client):
    """Valid credentials return 200 with user info."""
    client.post(
        "/auth/register",
        json={
            "username": "loginuser",
            "email": "login@example.com",
            "password": STRONG_PW,
            "confirm_password": STRONG_PW,
        },
    )
    resp = client.post(
        "/auth/login",
        json={"username": "loginuser", "password": STRONG_PW},
    )
    assert resp.status_code == 200
    assert resp.get_json()["user"]["username"] == "loginuser"


def test_login_wrong_password(client):
    """Wrong password returns a non-200 error response."""
    client.post(
        "/auth/register",
        json={
            "username": "userX",
            "email": "x@example.com",
            "password": STRONG_PW,
            "confirm_password": STRONG_PW,
        },
    )
    resp = client.post(
        "/auth/login",
        json={"username": "userX", "password": "WrongPass99!"},
    )
    # 401 for bad credentials; 400 is also acceptable if form validation fires first
    assert resp.status_code in (400, 401)


def test_login_nonexistent_user(client):
    """Login for an unknown username returns a client-error response."""
    resp = client.post(
        "/auth/login",
        json={"username": "nobody", "password": STRONG_PW},
    )
    assert resp.status_code in (400, 401)


# ── Projects require auth ─────────────────────────────────────────────────────

def test_list_projects_unauthenticated(client):
    """GET /projects/ without auth returns 401."""
    resp = client.get("/projects/")
    assert resp.status_code == 401


def test_create_project_unauthenticated(client):
    """POST /projects/ without auth returns 401."""
    resp = client.post("/projects/", json={"name": "test"})
    assert resp.status_code == 401


# ── Authenticated project / experiment flow ───────────────────────────────────

def test_list_projects_authenticated(auth_client):
    """Authenticated user can list projects."""
    resp = auth_client.get("/projects/")
    assert resp.status_code == 200
    assert "projects" in resp.get_json()


def test_create_and_get_project(auth_client):
    """Authenticated user can create then retrieve a project."""
    resp = auth_client.post(
        "/projects/",
        json={"name": "Smoke Project", "description": "CI test"},
    )
    assert resp.status_code == 201
    project_id = resp.get_json()["project"]["id"]

    resp2 = auth_client.get(f"/projects/{project_id}")
    assert resp2.status_code == 200
    assert resp2.get_json()["project"]["name"] == "Smoke Project"


def test_create_project_missing_name(auth_client):
    """Creating a project without a name returns 400."""
    resp = auth_client.post("/projects/", json={"description": "no name"})
    assert resp.status_code == 400


def test_create_experiment_in_project(auth_client):
    """Authenticated user can create an experiment inside a project."""
    proj = auth_client.post(
        "/projects/", json={"name": "Exp Project"}
    ).get_json()["project"]

    resp = auth_client.post(
        f"/experiments/{proj['id']}",
        json={"name": "First Experiment"},
    )
    assert resp.status_code == 201
    exp = resp.get_json()["experiment"]
    assert exp["name"] == "First Experiment"
    assert exp["status"] == "created"


def test_delete_project(auth_client):
    """Authenticated user can delete their own project."""
    proj_id = auth_client.post(
        "/projects/",
        json={"name": "To Delete"},
    ).get_json()["project"]["id"]

    resp = auth_client.delete(f"/projects/{proj_id}")
    assert resp.status_code == 200

    # Confirm it's gone
    assert auth_client.get(f"/projects/{proj_id}").status_code == 404
