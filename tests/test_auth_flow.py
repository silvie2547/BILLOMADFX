"""Authentication flow: register, sign in, stay signed in, revoke on logout.

Also covers the abuse protection (lockout, per-IP limits), the password
policy and the security headers middleware.
"""
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import ratelimit
from app.database import Base, get_db
from app.main import app

STRONG_PASSWORD = "Gold-Platform-2026!"


@pytest.fixture
def auth_client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    test_sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_db():
        with test_sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    ratelimit.reset_all()
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    ratelimit.reset_all()


def register(client: TestClient, email: str, password: str = STRONG_PASSWORD, name: str = "Trader") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": name},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_register_then_stays_signed_in(auth_client: TestClient):
    data = register(auth_client, "trader1@example.com")
    assert data["user"]["email"] == "trader1@example.com"
    assert data["user"]["role"] == "user"
    assert data["access_token"]

    me = auth_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "trader1@example.com"


def test_login_after_register(auth_client: TestClient):
    register(auth_client, "trader2@example.com")
    response = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "trader2@example.com", "password": STRONG_PASSWORD},
    )
    assert response.status_code == 200
    me = auth_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"})
    assert me.status_code == 200


def test_register_rejects_weak_passwords(auth_client: TestClient):
    cases = {
        "alllowercase123": "uppercase",
        "ALLUPPERCASE123": "lowercase",
        "NoDigitsHere": "number",
    }
    for password, missing in cases.items():
        response = auth_client.post(
            "/api/v1/auth/register",
            json={"email": f"weak-{missing}@example.com", "password": password, "display_name": "Trader"},
        )
        assert response.status_code == 422, response.text
        assert missing in response.text
    too_short = auth_client.post(
        "/api/v1/auth/register",
        json={"email": "weak-short@example.com", "password": "Sh0rt!", "display_name": "Trader"},
    )
    assert too_short.status_code == 422


def test_register_rejects_password_containing_email(auth_client: TestClient):
    response = auth_client.post(
        "/api/v1/auth/register",
        json={"email": "mailman@example.com", "password": "Mailman12abcX", "display_name": "Trader"},
    )
    assert response.status_code == 422
    assert "email address" in response.text


def test_register_duplicate_email_conflict(auth_client: TestClient):
    register(auth_client, "duplicate@example.com")
    response = auth_client.post(
        "/api/v1/auth/register",
        json={"email": "duplicate@example.com", "password": STRONG_PASSWORD, "display_name": "Again"},
    )
    assert response.status_code == 409


def test_login_lockout_after_repeated_failures(auth_client: TestClient):
    register(auth_client, "locked@example.com")
    for _ in range(5):
        failed = auth_client.post(
            "/api/v1/auth/login",
            json={"email": "locked@example.com", "password": "WrongPassword1"},
        )
        assert failed.status_code == 401
    # Even the correct password is refused while the account is locked.
    locked = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "locked@example.com", "password": STRONG_PASSWORD},
    )
    assert locked.status_code == 429
    assert "locked" in locked.json()["detail"]


def test_register_per_ip_rate_limit(auth_client: TestClient):
    for index in range(8):
        response = auth_client.post(
            "/api/v1/auth/register",
            json={"email": f"bulk{index}@example.com", "password": STRONG_PASSWORD, "display_name": "Bulk"},
        )
        assert response.status_code == 201, response.text
    blocked = auth_client.post(
        "/api/v1/auth/register",
        json={"email": "bulk9@example.com", "password": STRONG_PASSWORD, "display_name": "Bulk"},
    )
    assert blocked.status_code == 429


def test_logout_revokes_token_everywhere(auth_client: TestClient):
    data = register(auth_client, "logout@example.com")
    token = data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert auth_client.get("/api/v1/auth/me", headers=headers).status_code == 200

    logout = auth_client.post("/api/v1/auth/logout", headers=headers)
    assert logout.status_code == 200
    assert logout.json()["logged_out"] is True

    revoked = auth_client.get("/api/v1/auth/me", headers=headers)
    assert revoked.status_code == 401

    # Re-signing in issues a working token again (new token version).
    fresh = auth_client.post(
        "/api/v1/auth/login",
        json={"email": "logout@example.com", "password": STRONG_PASSWORD},
    )
    assert fresh.status_code == 200
    assert auth_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {fresh.json()['access_token']}"}).status_code == 200


def test_refresh_sliding_session(auth_client: TestClient):
    data = register(auth_client, "sliding@example.com")
    old_token = data["access_token"]
    response = auth_client.post("/api/v1/auth/refresh", headers={"Authorization": f"Bearer {old_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"] and body["access_token"] != old_token
    me = auth_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200


def test_refresh_rejects_invalid_token(auth_client: TestClient):
    response = auth_client.post("/api/v1/auth/refresh", headers={"Authorization": "Bearer not-a-token"})
    assert response.status_code == 401


def test_security_headers(auth_client: TestClient):
    page = auth_client.get("/")
    assert page.status_code == 200
    assert page.headers["X-Content-Type-Options"] == "nosniff"
    assert page.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in page.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in page.headers["Content-Security-Policy"]

    meta = auth_client.get("/api/v1/meta")
    assert meta.status_code == 200
    assert meta.headers["Cache-Control"] == "no-store"
