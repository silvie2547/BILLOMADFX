"""Demo-only MetaTrader 5 read integration.

This module intentionally cannot send, modify, or close orders.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class Mt5Status:
    available: bool
    initialized: bool
    connected: bool
    demo: bool
    account_mode: str
    trade_allowed: bool
    tradeapi_disabled: bool
    server: str | None
    login_last4: str | None
    error: str | None = None


class Mt5ReadService:
    """Read MT5 terminal/account/market data with a strict demo-only policy."""

    def __init__(self, terminal_path: str | None = None) -> None:
        self.terminal_path = terminal_path or os.getenv("MT5_TERMINAL_PATH")
        self._mt5: Any | None = None

    def _load(self) -> tuple[Any | None, str | None]:
        try:
            import MetaTrader5 as mt5
            return mt5, None
        except ImportError:
            return None, "MetaTrader5 Python package is not installed"

    def status(self) -> Mt5Status:
        mt5, error = self._load()
        if mt5 is None:
            return Mt5Status(False, False, False, False, "UNAVAILABLE", False, True, None, None, error)

        try:
            initialized = mt5.initialize(path=self.terminal_path) if self.terminal_path else mt5.initialize()
            if not initialized:
                code, detail = mt5.last_error()
                return Mt5Status(True, False, False, False, "UNKNOWN", False, True, None, None, f"Cannot initialize MT5: {code} {detail}")

            terminal = mt5.terminal_info()
            account = mt5.account_info()
            if terminal is None or account is None:
                return Mt5Status(True, True, False, False, "UNKNOWN", False, True, None, None, "Terminal or account information unavailable")

            mode = "DEMO" if account.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO else "REAL" if account.trade_mode == mt5.ACCOUNT_TRADE_MODE_REAL else "OTHER"
            return Mt5Status(
                available=True,
                initialized=True,
                connected=bool(terminal.connected),
                demo=mode == "DEMO",
                account_mode=mode,
                trade_allowed=bool(terminal.trade_allowed),
                tradeapi_disabled=bool(terminal.tradeapi_disabled),
                server=str(account.server),
                login_last4=str(account.login)[-4:],
            )
        finally:
            mt5.shutdown()

    def _require_demo_session(self) -> Any:
        mt5, error = self._load()
        if mt5 is None:
            raise PermissionError(error)
        initialized = mt5.initialize(path=self.terminal_path) if self.terminal_path else mt5.initialize()
        if not initialized:
            raise PermissionError("MT5 terminal could not be initialized")

        try:
            terminal = mt5.terminal_info()
            account = mt5.account_info()
            if terminal is None or account is None:
                raise PermissionError("MT5 terminal/account information unavailable")
            if not terminal.connected:
                raise PermissionError("MT5 terminal is disconnected")
            if account.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
                raise PermissionError("Only DEMO MT5 accounts may be accessed")
            return mt5
        except Exception:
            # Never leave an initialized terminal session behind on a rejected session.
            mt5.shutdown()
            raise

    def account(self) -> dict[str, Any]:
        mt5 = self._require_demo_session()
        try:
            account = mt5.account_info()
            if account is None:
                raise PermissionError("MT5 account information unavailable")
            return {
                "mode": "DEMO",
                "server": str(account.server),
                "login_last4": str(account.login)[-4:],
                "balance": float(account.balance),
                "equity": float(account.equity),
                "currency": str(account.currency),
                "margin_free": float(account.margin_free),
            }
        finally:
            mt5.shutdown()

    def positions(self) -> list[dict[str, Any]]:
        mt5 = self._require_demo_session()
        try:
            raw = mt5.positions_get(symbol="XAUUSD")
            if raw is None:
                return []
            return [
                {
                    "ticket": int(position.ticket),
                    "symbol": str(position.symbol),
                    "type": "BUY" if position.type == mt5.POSITION_TYPE_BUY else "SELL",
                    "volume": float(position.volume),
                    "entry": float(position.price_open),
                    "current": float(position.price_current),
                    "profit": float(position.profit),
                    "stop_loss": float(position.sl),
                    "take_profit": float(position.tp),
                }
                for position in raw
            ]
        finally:
            mt5.shutdown()

    def bars(self, timeframe: str = "H1", count: int = 100) -> list[dict[str, Any]]:
        mt5 = self._require_demo_session()
        try:
            allowed = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
                       "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
                       "D1": mt5.TIMEFRAME_D1}
            tf = allowed.get(timeframe.upper())
            if tf is None:
                raise ValueError("Unsupported timeframe")
            count = max(1, min(count, 500))
            rates = mt5.copy_rates_from_pos("XAUUSD", tf, 0, count)
            if rates is None:
                return []
            return [
                {
                    "time": datetime.fromtimestamp(int(rate["time"]), timezone.utc).isoformat(),
                    "open": float(rate["open"]),
                    "high": float(rate["high"]),
                    "low": float(rate["low"]),
                    "close": float(rate["close"]),
                    "tick_volume": int(rate["tick_volume"]),
                    "spread": int(rate["spread"]),
                }
                for rate in rates
            ]
        finally:
            mt5.shutdown()


def mt5_status_dict() -> dict[str, Any]:
    return asdict(Mt5ReadService().status())
