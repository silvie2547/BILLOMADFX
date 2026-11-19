from fastapi import APIRouter, Depends, HTTPException, Query, status

from .dependencies import get_current_user
from .mt5 import Mt5ReadService

router = APIRouter(prefix="/api/v1/mt5", tags=["MetaTrader 5 read-only"])


def mt5_service() -> Mt5ReadService:
    return Mt5ReadService()


@router.get("/status")
def mt5_status(service: Mt5ReadService = Depends(mt5_service), user=Depends(get_current_user)):
    status_value = service.status()
    return {
        "available": status_value.available,
        "initialized": status_value.initialized,
        "connected": status_value.connected,
        "demo": status_value.demo,
        "account_mode": status_value.account_mode,
        "trade_allowed": status_value.trade_allowed,
        "tradeapi_disabled": status_value.tradeapi_disabled,
        "server": status_value.server,
        "login_last4": status_value.login_last4,
        "error": status_value.error,
    }


@router.get("/account")
def mt5_account(service: Mt5ReadService = Depends(mt5_service), user=Depends(get_current_user)):
    try:
        return service.account()
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.get("/positions")
def mt5_positions(service: Mt5ReadService = Depends(mt5_service), user=Depends(get_current_user)):
    try:
        items = service.positions()
        return {"items": items, "count": len(items), "mode": "DEMO"}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.get("/bars")
def mt5_bars(
    timeframe: str = Query("H1", pattern="^[Mm][15]|M1|M5|M15|M30|H1|H4|D1$"),
    count: int = Query(100, ge=1, le=500),
    service: Mt5ReadService = Depends(mt5_service),
    user=Depends(get_current_user),
):
    try:
        return {"symbol": "XAUUSD", "timeframe": timeframe.upper(), "items": service.bars(timeframe, count)}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
