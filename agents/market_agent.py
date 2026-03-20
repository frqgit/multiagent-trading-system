"""Market Analyst Agent — fetches stock data and computes technical indicators."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from tools.stock_api import StockSnapshot, fetch_stock_data

logger = logging.getLogger(__name__)


def _fmt_mcap(val: int) -> str:
    if val >= 1_000_000_000_000:
        return f"${val / 1_000_000_000_000:.2f}T"
    if val >= 1_000_000_000:
        return f"${val / 1_000_000_000:.2f}B"
    if val >= 1_000_000:
        return f"${val / 1_000_000:.2f}M"
    return f"${val:,}"


def _fmt_vol(val: int) -> str:
    if val >= 1_000_000:
        return f"{val / 1_000_000:.1f}M"
    if val >= 1_000:
        return f"{val / 1_000:.1f}K"
    return str(val)


class MarketAnalystAgent:
    """Retrieves and interprets market data for a given stock symbol."""

    name = "MarketAnalystAgent"

    async def analyze(self, symbol: str) -> dict[str, Any]:
        logger.info("[%s] Analyzing %s", self.name, symbol)
        last_error = None
        for attempt in range(2):  # 1 retry
            try:
                s: StockSnapshot = await asyncio.to_thread(fetch_stock_data, symbol)
                break
            except Exception as exc:
                last_error = exc
                if attempt == 0:
                    logger.warning("[%s] Attempt 1 failed for %s: %s — retrying", self.name, symbol, exc)
                    await asyncio.sleep(1)
                else:
                    logger.error("[%s] All attempts failed for %s: %s", self.name, symbol, exc)
                    return {"error": str(exc), "symbol": symbol}
        else:
            return {"error": str(last_error), "symbol": symbol}

        signals: list[str] = []

        # Moving-average signals
        if s.ma20 > s.ma50:
            signals.append("MA20 > MA50 — short-term bullish crossover")
        else:
            signals.append("MA20 < MA50 — short-term bearish crossover")

        if s.ma50 > s.ma200:
            signals.append("MA50 > MA200 — golden cross (long-term bullish)")
        elif s.ma50 < s.ma200:
            signals.append("MA50 < MA200 — death cross (long-term bearish)")

        # MACD
        if s.macd > s.macd_signal:
            signals.append(f"MACD ({s.macd:.4f}) above signal ({s.macd_signal:.4f}) — bullish momentum")
        else:
            signals.append(f"MACD ({s.macd:.4f}) below signal ({s.macd_signal:.4f}) — bearish momentum")

        # RSI
        if s.rsi > 70:
            signals.append(f"RSI {s.rsi} — overbought territory")
        elif s.rsi < 30:
            signals.append(f"RSI {s.rsi} — oversold territory (potential bounce)")
        elif s.rsi > 60:
            signals.append(f"RSI {s.rsi} — upper neutral (approaching overbought)")
        elif s.rsi < 40:
            signals.append(f"RSI {s.rsi} — lower neutral (approaching oversold)")
        else:
            signals.append(f"RSI {s.rsi} — neutral zone")

        # Volatility
        if s.volatility > 40:
            signals.append(f"High volatility ({s.volatility}% ann.) — caution advised")
        elif s.volatility > 25:
            signals.append(f"Moderate volatility ({s.volatility}% ann.)")
        else:
            signals.append(f"Low volatility ({s.volatility}% ann.) — stable")

        # Volume
        if s.avg_volume and s.volume > s.avg_volume * 1.5:
            signals.append(f"Volume surge: {_fmt_vol(s.volume)} vs avg {_fmt_vol(s.avg_volume)}")
        elif s.avg_volume and s.volume < s.avg_volume * 0.5:
            signals.append(f"Low volume: {_fmt_vol(s.volume)} vs avg {_fmt_vol(s.avg_volume)}")

        # 52-week position
        week52_range = s.week52_high - s.week52_low
        if week52_range > 0:
            position = (s.current_price - s.week52_low) / week52_range * 100
            signals.append(f"Trading at {position:.0f}% of 52-week range (${s.week52_low} – ${s.week52_high})")

        return {
            "symbol": s.symbol,
            "company_name": s.company_name,
            "sector": s.sector,
            "price": s.current_price,
            "previous_close": s.previous_close,
            "open": s.open_price,
            "day_high": s.day_high,
            "day_low": s.day_low,
            "week52_high": s.week52_high,
            "week52_low": s.week52_low,
            "volume": s.volume,
            "volume_formatted": _fmt_vol(s.volume),
            "avg_volume": s.avg_volume,
            "market_cap": s.market_cap,
            "market_cap_formatted": _fmt_mcap(s.market_cap) if s.market_cap else "N/A",
            "pe_ratio": s.pe_ratio,
            "eps": s.eps,
            "dividend_yield": s.dividend_yield,
            "ma20": s.ma20,
            "ma50": s.ma50,
            "ma200": s.ma200,
            "ema12": s.ema12,
            "ema26": s.ema26,
            "macd": s.macd,
            "macd_signal": s.macd_signal,
            "rsi": s.rsi,
            "volatility": s.volatility,
            "beta": s.beta,
            "trend": s.trend,
            "price_change": s.price_change,
            "price_change_pct": s.price_change_pct,
            "price_history_30d": s.price_history_30d,
            "signals": signals,
            "fetched_at": s.fetched_at,
        }
