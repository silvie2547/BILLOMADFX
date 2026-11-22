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


def test_positions_fail_closed_without_meta_trader(monkeypatch):
    """positions() must raise PermissionError when the MT5 package is unavailable."""
    service = Mt5ReadService()
    monkeypatch.setattr(service, "_load", lambda: (None, "MetaTrader5 Python package is not installed"))
    with pytest.raises(PermissionError, match="MetaTrader5 Python package is not installed"):
        service.positions()
