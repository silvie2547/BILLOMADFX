"""Live market data for gold (XAU) from free public sources.

Every value returned by this module is real, freshly fetched market data.
Nothing is synthesized, interpolated, or cached beyond the short TTLs below.

Providers (both keyless and free):
- gold-api.com        -> spot XAU price in USD (quoted per troy ounce).
- Binance public REST -> tokenized gold (PAXG/USDT) OHLC candles. PAXG is a
  gold-backed token (1 token = 1 troy ounce of London Good Delivery gold),
  so its candles are a live proxy for XAUUSD price action on exchanges that
  trade around the clock.

If a provider is unreachable the service reports ``available: False`` with the
provider error instead of inventing data.
"""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any

SPOT_URL = "https://api.gold-api.com/price/XAU"
BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
BINANCE_SYMBOL = "PAXGUSDT"

# Engine timeframes -> Binance kline intervals (the spot provider has no history).
SUPPORTED_TIMEFRAMES: dict[str, str] = {"M15": "15m", "H1": "1h", "H4": "4h", "D1": "1d"}

QUOTE_TTL_SECONDS = 30
CANDLES_TTL_SECONDS = 60
HTTP_TIMEOUT_SECONDS = 10
MAX_CANDLES = 500


def _fetch_json(url: str, timeout: int = HTTP_TIMEOUT_SECONDS) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": "BILLOMADFX/0.0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _utc_iso(timestamp_ms: int | None = None) -> str:
    if timestamp_ms is None:
        return datetime.now(timezone.utc).isoformat()
    return datetime.fromtimestamp(timestamp_ms / 1000, timezone.utc).isoformat()


class MarketDataService:
    """Fetches spot quotes, candles, and a rule-based trend read on demand."""

    def __init__(self) -> None:
        self._spot_cache: tuple[float, dict[str, Any]] | None = None
        self._candles_cache: tuple[float, str, list[dict[str, Any]]] | None = None

    # ------------------------------------------------------------------ spot
    def spot_quote(self) -> dict[str, Any]:
        now = time.monotonic()
        if self._spot_cache and now - self._spot_cache[0] < QUOTE_TTL_SECONDS:
            return self._spot_cache[1]
        try:
            payload = _fetch_json(SPOT_URL)
            price = float(payload["price"])
            if price <= 0:
                raise ValueError("non-positive price")
            quote = {
                "available": True,
                "symbol": "XAU",
                "name": "Gold spot",
                "currency": "USD",
                "price": price,
                "source": "gold-api.com",
                "updated_at": payload.get("updatedAt") or _utc_iso(),
            }
        except Exception as exc:  # noqa: BLE001 - report any provider failure honestly
            quote = {"available": False, "symbol": "XAU", "price": None, "source": "gold-api.com",
                     "error": f"Spot provider unavailable: {exc.__class__.__name__}"}
        self._spot_cache = (now, quote)
        return quote

    # --------------------------------------------------------------- candles
    def candles(self, timeframe: str = "H1", count: int = 100) -> dict[str, Any]:
        if timeframe not in SUPPORTED_TIMEFRAMES:
            raise ValueError("Unsupported timeframe")
        count = max(1, min(count, MAX_CANDLES))
        now = time.monotonic()
        if self._candles_cache and now - self._candles_cache[0] < CANDLES_TTL_SECONDS \
                and self._candles_cache[1] == timeframe and len(self._candles_cache[2]) >= count:
            items = self._candles_cache[2][-count:]
            return self._candle_payload(True, timeframe, items)

        interval = SUPPORTED_TIMEFRAMES[timeframe]
        try:
            url = f"{BINANCE_KLINES_URL}?symbol={BINANCE_SYMBOL}&interval={interval}&limit={count}"
            rows = _fetch_json(url)
            items = [
                {
                    "time": _utc_iso(int(row[0])),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]),
                }
                for row in rows
            ]
        except Exception as exc:  # noqa: BLE001
            return self._candle_payload(False, timeframe, [], f"Candle provider unavailable: {exc.__class__.__name__}")
        self._candles_cache = (now, timeframe, items)
        return self._candle_payload(True, timeframe, items)

    @staticmethod
    def _candle_payload(available: bool, timeframe: str, items: list[dict[str, Any]], error: str | None = None) -> dict[str, Any]:
        return {
            "available": available,
            "symbol": BINANCE_SYMBOL,
            "symbol_description": "Tokenized gold (1 PAXG = 1 troy ounce)",
            "timeframe": timeframe,
            "source": "Binance public REST",
            "items": items,
            "count": len(items),
            "error": error,
        }

    # ----------------------------------------------------------------- trend
    def trend(self, timeframe: str = "H1") -> dict[str, Any]:
        """Rule-based trend read from real candles (EMA20/EMA50 + RSI14).

        This is a transparent technical indicator, not a validated trading
        strategy and not financial advice; it never issues trade orders.
        """
        data = self.candles(timeframe, 200)
        if not data["available"] or data["count"] < 60:
            return {
                "available": False, "timeframe": timeframe, "trend": "UNAVAILABLE",
                "ema20": None, "ema50": None, "rsi14": None,
                "reason": data["error"] or "Not enough live candle history.",
                "generated_at": _utc_iso(),
            }
        closes = [bar["close"] for bar in data["items"]]
        ema20 = _ema(closes, 20)
        ema50 = _ema(closes, 50)
        rsi14 = _rsi(closes, 14)
        if ema20 > ema50 and rsi14 < 70:
            trend, reason = "BULLISH", "EMA20 is above EMA50 and RSI14 is below overbought (70)."
        elif ema20 < ema50 and rsi14 > 30:
            trend, reason = "BEARISH", "EMA20 is below EMA50 and RSI14 is above oversold (30)."
        else:
            trend = "NEUTRAL"
            reason = "Moving averages and RSI disagree; momentum is mixed."
        return {
            "available": True, "timeframe": timeframe, "trend": trend,
            "ema20": round(ema20, 2), "ema50": round(ema50, 2), "rsi14": round(rsi14, 1),
            "reason": reason, "generated_at": _utc_iso(),
            "source": "Binance public REST (PAXG/USDT)",
        }


def _ema(values: list[float], period: int) -> float:
    if len(values) < period:
        return values[-1]
    alpha = 2 / (period + 1)
    ema = sum(values[:period]) / period
    for value in values[period:]:
        ema = alpha * value + (1 - alpha) * ema
    return ema


def _rsi(values: list[float], period: int = 14) -> float:
    if len(values) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(values)):
        change = values[i] - values[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))
