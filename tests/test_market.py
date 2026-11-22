"""Tests for the live market data endpoints (providers are stubbed)."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.main import app, market_service


@pytest.fixture
def client():
    original = app.dependency_overrides.get(get_current_user)
    fake_user = SimpleNamespace(id=1, role="user",
                                risk_settings=SimpleNamespace(is_halted=False, daily_loss_limit_pct=2.0))
    app.dependency_overrides[get_current_user] = lambda: fake_user
    yield TestClient(app)
    if original is None:
        app.dependency_overrides.pop(get_current_user, None)
    else:
        app.dependency_overrides[get_current_user] = original


def test_market_endpoints_require_authentication():
    client = TestClient(app)
    assert client.get("/api/v1/market/quote").status_code == 401
    assert client.get("/api/v1/market/candles").status_code == 401
    assert client.get("/api/v1/market/trend").status_code == 401


def test_meta_is_public_and_versioned():
    data = TestClient(app).get("/api/v1/meta").json()
    assert data["version"] == "0.0.1"
    assert data["order_execution"] is False
    assert "gold-api.com" in data["market_sources"][0]


def test_quote_returns_real_shape(client, monkeypatch):
    monkeypatch.setattr(market_service, "spot_quote", lambda: {
        "available": True, "symbol": "XAU", "currency": "USD",
        "price": 3539.0, "source": "gold-api.com", "updated_at": "2026-11-22T10:00:00Z",
    })
    data = client.get("/api/v1/market/quote").json()
    assert data["available"] is True
    assert data["price"] == 3539.0


def test_candles_reject_unknown_timeframe(client):
    assert client.get("/api/v1/market/candles?timeframe=X").status_code == 422


def test_trend_reads_real_candles(client, monkeypatch):
    def fake_candles(timeframe, count):
        # Up 2, down 1 rhythm: net uptrend (EMA20 > EMA50) with real pullbacks
        # so RSI stays below the overbought band.
        closes, value = [], 3500.0
        for i in range(150):
            value += 2 if i % 2 == 0 else -1
            closes.append(value)
        items = [{"time": "2026-01-01T00:00:00+00:00", "open": c, "high": c + 1,
                  "low": c - 1, "close": c, "volume": 1} for c in closes]
        return {"available": True, "items": items, "count": len(items), "error": None}

    monkeypatch.setattr(market_service, "candles", fake_candles)
    data = client.get("/api/v1/market/trend").json()
    assert data["available"] is True
    assert data["trend"] == "BULLISH"
    assert data["ema20"] > data["ema50"]


def test_trend_fails_honest_without_data(client, monkeypatch):
    monkeypatch.setattr(market_service, "candles", lambda tf, c: {
        "available": False, "items": [], "count": 0, "error": "provider down"})
    data = client.get("/api/v1/market/trend").json()
    assert data["available"] is False
    assert data["trend"] == "UNAVAILABLE"
    assert "provider down" in data["reason"]


def test_dashboard_includes_live_market_block(client, monkeypatch):
    monkeypatch.setattr(market_service, "spot_quote", lambda: {
        "available": True, "price": 3539.0, "source": "gold-api.com", "updated_at": "2026-11-22T10:00:00Z"})
    monkeypatch.setattr(market_service, "trend", lambda tf: {
        "available": True, "trend": "BULLISH", "reason": "EMA20 above EMA50",
        "ema20": 3540.0, "ema50": 3530.0, "rsi14": 61.0, "timeframe": "H1"})
    data = client.get("/api/v1/dashboard").json()
    assert data["market"]["quote"]["price"] == 3539.0
    assert data["market"]["trend"]["trend"] == "BULLISH"
    assert data["data_mode"] == "live"
