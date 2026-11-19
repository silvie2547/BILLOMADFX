import pytest

from app.mt5 import Mt5ReadService


def test_status_fails_closed_without_meta_trader(monkeypatch):
    service = Mt5ReadService()
    monkeypatch.setattr(service, "_load", lambda: (None, "MetaTrader5 Python package is not installed"))
    status = service.status()
    assert status.available is False
    assert status.demo is False
    assert status.initialized is False
    assert status.error is not None


def test_bars_rejects_positions_without_demo(monkeypatch):
    service = Mt5ReadService()

    class FakeMt5:
        pass

    monkeypatch.setattr(service, "_load", lambda: (None, "missing"))
    with pytest.raises(PermissionError):
        service.positions()
