"""Stock market data fetcher using yfinance — with company info & MACD."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import yfinance as yf

logger = logging.getLogger(__name__)


@dataclass
class StockSnapshot:
    symbol: str
    company_name: str
    sector: str
    current_price: float
    previous_close: float
    open_price: float
    day_high: float
    day_low: float
    week52_high: float
    week52_low: float
    volume: int
    avg_volume: int
    market_cap: int
    pe_ratio: float | None
    eps: float | None
    dividend_yield: float | None
    ma20: float
    ma50: float
    ma200: float
    ema12: float
    ema26: float
    macd: float
    macd_signal: float
    rsi: float
    volatility: float
    beta: float | None
    trend: str  # "bullish" | "bearish" | "sideways"
    price_change: float
    price_change_pct: float
    price_history_30d: list[dict]
    fetched_at: str

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if k != "price_history_30d"} | {
            "price_history_30d": self.price_history_30d,
        }


def _compute_rsi(prices: np.ndarray, period: int = 14) -> float:
    """Compute RSI using exponential moving average (Wilder's method)."""
    if len(prices) < period + 1:
        return 50.0
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    alpha = 1.0 / period
    avg_gain = float(gains[0])
    avg_loss = float(losses[0])
    for i in range(1, len(gains)):
        avg_gain = alpha * float(gains[i]) + (1 - alpha) * avg_gain
        avg_loss = alpha * float(losses[i]) + (1 - alpha) * avg_loss

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100.0 - (100.0 / (1.0 + rs)))


def _ema(prices: np.ndarray, span: int) -> float:
    """Exponential moving average (last value)."""
    if len(prices) < span:
        return float(np.mean(prices))
    alpha = 2.0 / (span + 1)
    ema_val = float(prices[0])
    for p in prices[1:]:
        ema_val = alpha * float(p) + (1 - alpha) * ema_val
    return ema_val


def _detect_trend(ma20: float, ma50: float, ma200: float, current: float) -> str:
    if current > ma20 > ma50 > ma200:
        return "strong_bullish"
    if current > ma20 > ma50:
        return "bullish"
    if current < ma20 < ma50 < ma200:
        return "strong_bearish"
    if current < ma20 < ma50:
        return "bearish"
    return "sideways"


def _safe(val, default=None):
    """Return val if it is a real number, else default."""
    if val is None:
        return default
    try:
        f = float(val)
        if np.isnan(f) or np.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


def fetch_stock_data(symbol: str, period: str = "6mo") -> StockSnapshot:
    """Fetch price history + company fundamentals and compute indicators."""
    logger.info("Fetching stock data for %s (period=%s)", symbol, period)
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period=period)

    if hist.empty:
        raise ValueError(f"No data returned for symbol: {symbol}")

    info = ticker.info or {}

    closes = hist["Close"].values.astype(float)
    current_price = float(closes[-1])
    open_price = float(hist["Open"].values[-1])
    day_high = float(hist["High"].values[-1])
    day_low = float(hist["Low"].values[-1])
    volume = int(hist["Volume"].values[-1])
    prev_close = float(closes[-2]) if len(closes) >= 2 else current_price

    # Moving averages
    ma20 = float(np.mean(closes[-20:])) if len(closes) >= 20 else float(np.mean(closes))
    ma50 = float(np.mean(closes[-50:])) if len(closes) >= 50 else float(np.mean(closes))
    ma200 = float(np.mean(closes[-200:])) if len(closes) >= 200 else float(np.mean(closes))

    # EMA & MACD
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd = ema12 - ema26
    # Signal line: 9-period EMA of MACD (approximate from recent closes)
    if len(closes) >= 35:
        macd_series = []
        for i in range(34, len(closes)):
            e12 = _ema(closes[: i + 1], 12)
            e26 = _ema(closes[: i + 1], 26)
            macd_series.append(e12 - e26)
        macd_signal = _ema(np.array(macd_series), 9)
    else:
        macd_signal = macd

    rsi = _compute_rsi(closes)

    # Volatility
    if len(closes) > 1:
        daily_returns = np.diff(closes) / closes[:-1]
        volatility = float(np.std(daily_returns) * np.sqrt(252) * 100)
    else:
        volatility = 0.0

    price_change = current_price - prev_close
    price_change_pct = (price_change / prev_close) * 100 if prev_close else 0

    trend = _detect_trend(ma20, ma50, ma200, current_price)

    # Last 30 trading days for sparkline
    dates = hist.index[-30:]
    price_history_30d = [
        {"date": d.strftime("%Y-%m-%d"), "close": round(float(c), 2)}
        for d, c in zip(dates, closes[-30:])
    ]

    return StockSnapshot(
        symbol=symbol.upper(),
        company_name=info.get("shortName") or info.get("longName") or symbol.upper(),
        sector=info.get("sector", "N/A"),
        current_price=round(current_price, 2),
        previous_close=round(prev_close, 2),
        open_price=round(open_price, 2),
        day_high=round(day_high, 2),
        day_low=round(day_low, 2),
        week52_high=round(_safe(info.get("fiftyTwoWeekHigh"), day_high), 2),
        week52_low=round(_safe(info.get("fiftyTwoWeekLow"), day_low), 2),
        volume=volume,
        avg_volume=int(_safe(info.get("averageVolume"), volume) or volume),
        market_cap=int(_safe(info.get("marketCap"), 0) or 0),
        pe_ratio=round(_safe(info.get("trailingPE")), 2) if _safe(info.get("trailingPE")) else None,
        eps=round(_safe(info.get("trailingEps")), 2) if _safe(info.get("trailingEps")) else None,
        dividend_yield=round(_safe(info.get("dividendYield"), 0) * 100, 2) if _safe(info.get("dividendYield")) else None,
        ma20=round(ma20, 2),
        ma50=round(ma50, 2),
        ma200=round(ma200, 2),
        ema12=round(ema12, 2),
        ema26=round(ema26, 2),
        macd=round(macd, 4),
        macd_signal=round(macd_signal, 4),
        rsi=round(rsi, 2),
        volatility=round(volatility, 2),
        beta=round(_safe(info.get("beta"), 1.0), 2) if _safe(info.get("beta")) else None,
        trend=trend,
        price_change=round(price_change, 2),
        price_change_pct=round(price_change_pct, 2),
        price_history_30d=price_history_30d,
        fetched_at=datetime.utcnow().isoformat(),
    )
