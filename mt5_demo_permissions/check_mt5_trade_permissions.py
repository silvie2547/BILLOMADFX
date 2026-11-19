"""Read-only diagnostic for the locally installed MT5 terminal.

Never sends or modifies an order; never accesses or prints account credentials.
"""
import json
import sys
from pathlib import Path


def emit(**values):
    print(json.dumps(values, ensure_ascii=True, default=str))

try:
    import MetaTrader5 as mt5
except ImportError:
    emit(error="MetaTrader5 Python package is not installed. Run: py -3 -m pip install MetaTrader5")
    sys.exit(2)

path = sys.argv[1] if len(sys.argv) > 1 else str(Path(r"C:\Program Files\MetaTrader 5\terminal64.exe"))
try:
    if not mt5.initialize(path=path, timeout=30000):
        emit(error="Cannot initialize MT5 terminal: " + str(mt5.last_error()))
        sys.exit(2)

    terminal = mt5.terminal_info()
    account = mt5.account_info()
    if terminal is None or account is None:
        emit(error="MT5 terminal/account information unavailable: " + str(mt5.last_error()))
        sys.exit(2)

    account_mode = (
        "DEMO" if account.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO
        else "REAL" if account.trade_mode == mt5.ACCOUNT_TRADE_MODE_REAL
        else "OTHER"
    )
    emit(
        account_type=account_mode,
        login_last4=str(account.login)[-4:],
        server=account.server,
        connected=bool(terminal.connected),
        trade_allowed=bool(terminal.trade_allowed),
        tradeapi_disabled=bool(terminal.tradeapi_disabled),
        account_trade_allowed=bool(account.trade_allowed),
        account_trade_expert=bool(account.trade_expert),
        terminal_path=str(terminal.path),
    )
finally:
    mt5.shutdown()
