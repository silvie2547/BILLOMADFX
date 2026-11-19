from collections.abc import Iterator

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies import get_current_user
from app.main import app
from app.models import User


@pytest.fixture
def risk_client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    test_sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    with test_sessions() as db:
        user = User(email="risk-test@example.com", password_hash="unused", display_name="Risk test")
        db.add(user)
        db.commit()
        user_id = user.id

    def override_db():
        with test_sessions() as db:
            yield db

    def override_user(db=Depends(get_db)):
        return db.get(User, user_id)

    previous_db = app.dependency_overrides.get(get_db)
    previous_user = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    try:
        yield TestClient(app)
    finally:
        if previous_db is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_db
        if previous_user is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = previous_user
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_risk_settings_are_persisted_and_halt_state_is_preserved(risk_client):
    preflight = risk_client.options(
        "/api/v1/risk",
        headers={
            "Origin": "http://localhost:8080",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert preflight.status_code == 200
    assert "PUT" in preflight.headers["access-control-allow-methods"]

    initial = risk_client.get("/api/v1/risk")
    assert initial.status_code == 200
    assert initial.json()["daily_loss_limit_pct"] == 2.0

    stopped = risk_client.post("/api/v1/risk/emergency-stop")
    assert stopped.status_code == 200

    updated = risk_client.put(
        "/api/v1/risk",
        json={
            "daily_loss_limit_pct": 1.0,
            "weekly_loss_limit_pct": 3.0,
            "max_drawdown_pct": 8.0,
            "max_spread_points": 25,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["daily_loss_limit_pct"] == 1.0
    assert updated.json()["is_halted"] is True
    assert risk_client.get("/api/v1/risk").json()["max_spread_points"] == 25


@pytest.mark.parametrize(
    "values",
    [
        {"daily_loss_limit_pct": 2.1, "weekly_loss_limit_pct": 3, "max_drawdown_pct": 8, "max_spread_points": 25},
        {"daily_loss_limit_pct": 1.5, "weekly_loss_limit_pct": 1, "max_drawdown_pct": 8, "max_spread_points": 25},
        {"daily_loss_limit_pct": 1, "weekly_loss_limit_pct": 8, "max_drawdown_pct": 8, "max_spread_points": 25},
        {"daily_loss_limit_pct": 1, "weekly_loss_limit_pct": 3, "max_drawdown_pct": 8, "max_spread_points": 41},
    ],
)
def test_risk_settings_reject_limits_outside_safe_bounds(risk_client, values):
    response = risk_client.put("/api/v1/risk", json=values)
    assert response.status_code == 422
