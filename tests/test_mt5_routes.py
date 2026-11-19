from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.main import app
from app.mt5 import Mt5Status
from app.mt5_routes import mt5_service


class FakeMt5ReadService:
    def status(self):
        return Mt5Status(True, True, True, True, "DEMO", False, True, "Demo-Server", "1234")

    def account(self):
        return {"mode": "DEMO", "server": "Demo-Server", "login_last4": "1234"}

    def positions(self):
        return [{"symbol": "XAUUSD", "type": "BUY", "volume": 0.1}]

    def bars(self, timeframe, count):
        return [{"timeframe": timeframe, "count": count}]


def test_mt5_routes_require_authentication():
    response = TestClient(app).get("/api/v1/mt5/status")
    assert response.status_code == 401


def test_mt5_read_routes_return_demo_data_and_validate_timeframes():
    original_user_dependency = app.dependency_overrides.get(get_current_user)
    original_service_dependency = app.dependency_overrides.get(mt5_service)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    app.dependency_overrides[mt5_service] = FakeMt5ReadService
    try:
        client = TestClient(app)
        assert client.get("/api/v1/mt5/status").json()["demo"] is True
        assert client.get("/api/v1/mt5/account").json()["mode"] == "DEMO"
        assert client.get("/api/v1/mt5/positions").json()["count"] == 1
        assert client.get("/api/v1/mt5/bars?timeframe=H1&count=12").json()["items"] == [
            {"timeframe": "H1", "count": 12}
        ]
        assert client.get("/api/v1/mt5/bars?timeframe=H1garbage").status_code == 422
    finally:
        if original_user_dependency is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = original_user_dependency
        if original_service_dependency is None:
            app.dependency_overrides.pop(mt5_service, None)
        else:
            app.dependency_overrides[mt5_service] = original_service_dependency
