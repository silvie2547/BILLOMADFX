"""Authentication flows: sign-up with one-time code, sign-in, sessions,
password reset, two-step authentication, and the abuse protection around them.

The test fixtures run without SMTP configured, so the API uses display mode:
one-time codes are returned in the HTTP response (field `otp`) instead of
being emailed — the documented self-host/development fallback.
"""
from collections.abc import Iterator

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import ratelimit
from app.database import Base, get_db, run_light_migrations
from app.main import app
from app.models import OtpCode

STRONG_PASSWORD = "Gold-Platform-2026!"


@pytest.fixture
def auth_client() -> Iterator[tuple[TestClient, sessionmaker]]:
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
    yield TestClient(app), test_sessions
    app.dependency_overrides.pop(get_db, None)
    ratelimit.reset_all()


def register(client: TestClient, email: str, password: str = STRONG_PASSWORD, name: str = "Trader") -> dict:
    """Sign up and confirm the verification code (display mode). Returns the
    verify-otp response, which carries the session token."""
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": name},
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["otp_required"] is True
    assert data["delivery"] == "display" and data["otp"], response.text
    assert data["expires_in_minutes"] == 20
    verify = client.post("/api/v1/auth/verify-otp", json={"email": email, "code": data["otp"]})
    assert verify.status_code == 200, verify.text
    return verify.json()


def sign_in(client: TestClient, email: str, password: str = STRONG_PASSWORD) -> dict:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def test_register_sends_otp_and_verifies(auth_client: tuple[TestClient, sessionmaker]):
    client, _ = auth_client
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "trader1@example.com", "password": STRONG_PASSWORD, "display_name": "Trader"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["otp_required"] is True
    assert data["delivery"] == "display"  # no SMTP in tests
    assert data["otp"] and data["otp"].isdigit() and len(data["otp"]) == 6

    # Not verified yet: login is refused with a steer back to the code screen.
    blocked = client.post("/api/v1/auth/login", json={"email": "trader1@example.com", "password": STRONG_PASSWORD})
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "email_not_verified"

    wrong = client.post("/api/v1/auth/verify-otp", json={"email": "trader1@example.com", "code": "000001"})
    assert wrong.status_code == 400

    ok = client.post("/api/v1/auth/verify-otp", json={"email": "trader1@example.com", "code": data["otp"]})
    assert ok.status_code == 200
    token = ok.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "trader1@example.com"
    assert me.json()["email_verified"] is True


def test_login_after_verification_and_me(auth_client: tuple[TestClient, sessionmaker]):
    client, _ = auth_client
    register(client, "trader2@example.com")
    data = sign_in(client, "trader2@example.com")
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
    assert me.status_code == 200


def test_register_rejects_weak_passwords(auth_client: tuple[TestClient, sessionmaker]):
    client, _ = auth_client
    cases = {
        "alllowercase123": "uppercase",
        "ALLUPPERCASE123": "lowercase",
        "NoDigitsHere": "number",
    }
    for password, missing in cases.items():
        response = client.post(
            "/api/v1/auth/register",
            json={"email": f"weak-{missing}@example.com", "password": password, "display_name": "Trader"},
        )
        assert response.status_code == 422, response.text
        assert missing in response.text
    too_short = client.post(
        "/api/v1/auth/register",
        json={"email": "weak-short@example.com", "password": "Sh0rt!", "display_name": "Trader"},
    )
    assert too_short.status_code == 422


def test_register_rejects_password_containing_email(auth_client: tuple[TestClient, sessionmaker]):
    client, _ = auth_client
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "mailman@example.com", "password": "Mailman12abcX", "display_name": "Trader"},
    )
    assert response.status_code == 422
    assert "email address" in response.text


def test_register_duplicate_email_conflict(auth_client: tuple[TestClient, sessionmaker]):
    client, _ = auth_client
    register(client, "duplicate@example.com")
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "duplicate@example.com", "password": STRONG_PASSWORD, "display_name": "Again"},
    )
    assert response.status_code == 409


def test_unverified_duplicate_resends_code(auth_client: tuple[TestClient, sessionmaker]):
    client, _ = auth_client
    first = client.post(
        "/api/v1/auth/register",
        json={"email": "pending@example.com", "password": STRONG_PASSWORD, "display_name": "P"},
    )
    assert first.status_code == 201
    # Same address again before verifying: a fresh code is issued, not an error.
    second = client.post(
        "/api/v1/auth/register",
        json={"email": "pending@example.com", "password": STRONG_PASSWORD, "display_name": "P"},
    )
    assert second.status_code == 201
    resent = second.json()
    assert resent["otp_required"] is True and resent["otp"]
    verify = client.post("/api/v1/auth/verify-otp", json={"email": "pending@example.com", "code": resent["otp"]})
    assert verify.status_code == 200


def test_signup_otp_expires_after_20_minutes(auth_client: tuple[TestClient, sessionmaker]):
    client, sessions = auth_client
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "expired@example.com", "password": STRONG_PASSWORD, "display_name": "T"},
    )
    code = response.json()["otp"]
    with sessions() as db:
        row = db.scalars(select(OtpCode).order_by(OtpCode.id.desc())).first()
        row.expires_at = row.expires_at.replace(year=row.expires_at.year - 1)  # 20 minutes long past
        db.commit()
    result = client.post("/api/v1/auth/verify-otp", json={"email": "expired@example.com", "code": code})
    assert result.status_code == 400
    assert "expired" in result.json()["detail"].lower()
    assert "20" in result.json()["detail"]


def test_signup_otp_resend_invalidates_previous_code(auth_client: tuple[TestClient, sessionmaker]):
    client, _ = auth_client
    first = client.post(
        "/api/v1/auth/register",
        json={"email": "resend@example.com", "password": STRONG_PASSWORD, "display_name": "T"},
    )
    old_code = first.json()["otp"]
    resend = client.post("/api/v1/auth/resend-otp", json={"email": "resend@example.com"})
    assert resend.status_code == 200
    resent = resend.json()
    assert resent["resent"] is True and resent["otp"] != old_code

    stale = client.post("/api/v1/auth/verify-otp", json={"email": "resend@example.com", "code": old_code})
    assert stale.status_code == 400

    fresh = client.post("/api/v1/auth/verify-otp", json={"email": "resend@example.com", "code": resent["otp"]})
    assert fresh.status_code == 200


def test_resend_otp_does_not_reveal_unknown_accounts(auth_client: tuple[TestClient, sessionmaker]):
    client, _ = auth_client
    known = client.post("/api/v1/auth/resend-otp", json={"email": "ghost@example.com"})
    assert known.status_code == 200
    body = known.json()
    assert body["resent"] is False
    assert "otp" not in body


def test_signup_otp_attempts_capped(auth_client: tuple[TestClient, sessionmaker]):
    client, _ = auth_client
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "capped@example.com", "password": STRONG_PASSWORD, "display_name": "T"},
    )
    code = response.json()["otp"]
    for attempt in range(5):
        wrong = client.post("/api/v1/auth/verify-otp", json={"email": "capped@example.com", "code": "000001"})
        assert wrong.status_code == 400
        if attempt < 4:
            assert "attempt" in wrong.json()["detail"].lower()
    # After 5 wrong tries the real code no longer works either.
    real = client.post("/api/v1/auth/verify-otp", json={"email": "capped@example.com", "code": code})
    assert real.status_code == 400
    assert "no active" in real.json()["detail"].lower()


def test_login_lockout_after_repeated_failures(auth_client: tuple[TestClient, sessionmaker]):
    client, _ = auth_client
    register(client, "locked@example.com")
    for _ in range(5):
        failed = client.post("/api/v1/auth/login", json={"email": "locked@example.com", "password": "WrongPassword1"})
        assert failed.status_code == 401
    locked = client.post("/api/v1/auth/login", json={"email": "locked@example.com", "password": STRONG_PASSWORD})
    assert locked.status_code == 429
    assert "locked" in locked.json()["detail"]


def test_register_per_ip_rate_limit(auth_client: tuple[TestClient, sessionmaker]):
    client, _ = auth_client
    for index in range(8):
        response = client.post(
            "/api/v1/auth/register",
            json={"email": f"bulk{index}@example.com", "password": STRONG_PASSWORD, "display_name": "Bulk"},
        )
        assert response.status_code == 201, response.text
    blocked = client.post(
        "/api/v1/auth/register",
        json={"email": "bulk9@example.com", "password": STRONG_PASSWORD, "display_name": "Bulk"},
    )
    assert blocked.status_code == 429


def test_logout_revokes_token_everywhere(auth_client: tuple[TestClient, sessionmaker]):
    client, _ = auth_client
    token = register(client, "logout@example.com")["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200

    logout = client.post("/api/v1/auth/logout", headers=headers)
    assert logout.status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401

    fresh = sign_in(client, "logout@example.com")
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {fresh['access_token']}"}).status_code == 200


def test_refresh_sliding_session(auth_client: tuple[TestClient, sessionmaker]):
    client, _ = auth_client
    old_token = register(client, "sliding@example.com")["access_token"]
    response = client.post("/api/v1/auth/refresh", headers={"Authorization": f"Bearer {old_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"] and body["access_token"] != old_token
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}).status_code == 200


def test_refresh_rejects_invalid_token(auth_client: tuple[TestClient, sessionmaker]):
    client, _ = auth_client
    assert client.post("/api/v1/auth/refresh", headers={"Authorization": "Bearer not-a-token"}).status_code == 401


def test_forgot_password_does_not_reveal_accounts(auth_client: tuple[TestClient, sessionmaker]):
    client, _ = auth_client
    unknown = client.post("/api/v1/auth/forgot-password", json={"email": "ghost@example.com"})
    assert unknown.status_code == 200
    assert "If an account exists" in unknown.json()["message"]
    assert "otp" not in unknown.json()


def test_password_reset_flow(auth_client: tuple[TestClient, sessionmaker]):
    client, sessions = auth_client
    old_token = register(client, "reset@example.com")["access_token"]

    forgot = client.post("/api/v1/auth/forgot-password", json={"email": "reset@example.com"})
    assert forgot.status_code == 200
    code = forgot.json()["otp"]  # display mode

    weak = client.post(
        "/api/v1/auth/reset-password",
        json={"email": "reset@example.com", "code": code, "new_password": "alllowercase123"},
    )
    assert weak.status_code == 422

    wrong_code = client.post(
        "/api/v1/auth/reset-password",
        json={"email": "reset@example.com", "code": "000001", "new_password": STRONG_PASSWORD},
    )
    assert wrong_code.status_code == 400

    reset = client.post(
        "/api/v1/auth/reset-password",
        json={"email": "reset@example.com", "code": code, "new_password": "Fresh-Password-2026"},
    )
    assert reset.status_code == 200
    assert reset.json()["password_reset"] is True

    # Every previous session is revoked by a password reset.
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_token}"}).status_code == 401
    # The reset code is single-use.
    reuse = client.post(
        "/api/v1/auth/reset-password",
        json={"email": "reset@example.com", "code": code, "new_password": "Fresh-Password-2026"},
    )
    assert reuse.status_code == 400
    # Sign-in works with the new password only.
    assert client.post("/api/v1/auth/login", json={"email": "reset@example.com", "password": STRONG_PASSWORD}).status_code == 401
    new_session = sign_in(client, "reset@example.com", "Fresh-Password-2026")
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_session['access_token']}"}).status_code == 200


def test_2fa_full_lifecycle(auth_client: tuple[TestClient, sessionmaker]):
    client, _ = auth_client
    register(client, "totp@example.com")

    setup = client.post("/api/v1/auth/2fa/setup")
    assert setup.status_code == 401  # requires a session

    session = sign_in(client, "totp@example.com")
    headers = {"Authorization": f"Bearer {session['access_token']}"}

    setup = client.post("/api/v1/auth/2fa/setup", headers=headers)
    assert setup.status_code == 200
    setup_data = setup.json()
    assert setup_data["otpauth_uri"].startswith("otpauth://totp/")
    assert setup_data["qr_data_uri"].startswith("data:image/png;base64,")
    assert len(setup_data["secret"]) >= 32

    confirm_wrong = client.post("/api/v1/auth/2fa/confirm", headers=headers, json={"code": "000001"})
    assert confirm_wrong.status_code == 400

    confirm = client.post("/api/v1/auth/2fa/confirm", headers=headers, json={"code": pyotp.TOTP(setup_data["secret"]).now()})
    assert confirm.status_code == 200
    assert confirm.json()["enabled"] is True
    backup_codes = confirm.json()["backup_codes"]
    assert len(backup_codes) == 8

    # Next sign-in needs the second step.
    challenge = client.post("/api/v1/auth/login", json={"email": "totp@example.com", "password": STRONG_PASSWORD})
    assert challenge.status_code == 200
    body = challenge.json()
    assert body["totp_required"] is True and body["challenge_token"]

    # The challenge token is not a session token.
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['challenge_token']}"}).status_code == 401

    finish = client.post("/api/v1/auth/login/2fa", json={"challenge_token": body["challenge_token"], "code": pyotp.TOTP(setup_data["secret"]).now()})
    assert finish.status_code == 200
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {finish.json()['access_token']}"}).status_code == 200

    # A backup code also completes a challenge — once.
    challenge2 = sign_in(client, "totp@example.com")
    backup = client.post(
        "/api/v1/auth/login/2fa",
        json={"challenge_token": challenge2["challenge_token"], "code": backup_codes[0]},
    )
    assert backup.status_code == 200

    challenge3 = sign_in(client, "totp@example.com")
    reuse = client.post(
        "/api/v1/auth/login/2fa",
        json={"challenge_token": challenge3["challenge_token"], "code": backup_codes[0]},
    )
    assert reuse.status_code == 401

    # Wrong codes are refused.
    wrong = client.post("/api/v1/auth/login/2fa", json={"challenge_token": challenge3["challenge_token"], "code": "000001"})
    assert wrong.status_code == 401

    # Disabling requires the account password.
    deny = client.post("/api/v1/auth/2fa/disable", headers=headers, json={"password": "WrongPassword1"})
    assert deny.status_code == 401
    allow = client.post("/api/v1/auth/2fa/disable", headers=headers, json={"password": STRONG_PASSWORD})
    assert allow.status_code == 200
    assert allow.json()["enabled"] is False

    # Back to plain password sign-in.
    direct = sign_in(client, "totp@example.com")
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {direct['access_token']}"}).status_code == 200


def test_security_headers(auth_client: tuple[TestClient, sessionmaker]):
    client, _ = auth_client
    page = client.get("/")
    assert page.status_code == 200
    assert page.headers["X-Content-Type-Options"] == "nosniff"
    assert page.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in page.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in page.headers["Content-Security-Policy"]

    meta = client.get("/api/v1/meta")
    assert meta.status_code == 200
    assert meta.headers["Cache-Control"] == "no-store"


def test_migration_upgrades_pre_existing_database(tmp_path):
    """A database created before email verification/2FA must keep working."""
    engine = create_engine(f"sqlite:///{tmp_path}/old.db")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(254), password_hash VARCHAR(255), "
            "display_name VARCHAR(80), role VARCHAR(16), is_active BOOLEAN, created_at DATETIME)"
        ))
        connection.execute(text(
            "INSERT INTO users (email, password_hash, display_name, role, is_active, created_at) "
            "VALUES ('old@example.com', 'x', 'Old', 'user', 1, '2026-01-01')"
        ))
    run_light_migrations(engine)
    columns = {column["name"] for column in inspect(engine).get_columns("users")}
    assert {"token_version", "email_verified", "two_factor_enabled", "totp_secret"} <= columns
    with engine.begin() as connection:
        row = connection.execute(text("SELECT email_verified, token_version FROM users")).fetchone()
    assert row.email_verified == 1  # pre-existing accounts are not locked out
    assert row.token_version == 0
