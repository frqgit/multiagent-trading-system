"""Technical Strategy Agent — Advanced technical analysis and multi-strategy signal generation.

Implements:
- Multi-timeframe analysis
- Advanced chart patterns (head & shoulders, double tops/bottoms, etc.)
- Fibonacci retracements and extensions
- Support/Resistance detection
- Ichimoku Cloud analysis
- Volume profile analysis
- Divergence detection
- Multiple oscillator confluence
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import yfinance as yf

logger = logging.getLogger(__name__)


@dataclass
class TechnicalSignal:
    """A technical trading signal."""
    signal_type: str  # BUY, SELL, HOLD
    strategy: str
    strength: float  # 0-1
    timeframe: str
    reason: str
    entry_price: float | None
    stop_loss: float | None
    target_price: float | None


class TechnicalStrategyAgent:
    """
    Advanced technical analysis with multiple strategies and timeframes.
    
    Capabilities:
    - Multi-timeframe trend analysis
    - Chart pattern recognition
    - Support/Resistance levels
    - Fibonacci analysis
    - Ichimoku Cloud
    - Volume analysis
    - Divergence detection
    - Oscillator confluence scoring
    """

    name = "TechnicalStrategyAgent"
    
    async def analyze(
        self,
        symbol: str,
        timeframe: str = "daily",
    ) -> dict[str, Any]:
        """
        Comprehensive technical analysis for a symbol.
        
        Args:
            symbol: Stock symbol
            timeframe: Analysis timeframe (intraday, daily, weekly)
            
        Returns:
            Technical analysis with signals, patterns, and levels
        """
        logger.info("[%s] Technical analysis for %s", self.name, symbol)
        
        # Fetch data
        try:
            data = await self._fetch_data(symbol, timeframe)
        except Exception as e:
            logger.error("[%s] Failed to fetch data: %s", self.name, e)
            return {"error": f"Failed to fetch data: {e}", "symbol": symbol}
        
        if data is None or len(data) < 50:
            return {"error": "Insufficient data", "symbol": symbol}
        
        closes = np.array([d["close"] for d in data])
        highs = np.array([d["high"] for d in data])
        lows = np.array([d["low"] for d in data])
        volumes = np.array([d["volume"] for d in data])
        
        # Calculate indicators
        indicators = self._calculate_indicators(closes, highs, lows, volumes)
        
        # Multi-timeframe trend
        mtf_trend = self._multi_timeframe_trend(closes)
        
        # Support/Resistance levels
        sr_levels = self._support_resistance(highs, lows, closes)
        
        # Fibonacci levels
        fib_levels = self._fibonacci_levels(highs, lows)
        
        # Chart patterns
        patterns = self._detect_patterns(closes, highs, lows, volumes)
        
        # Ichimoku Cloud
        ichimoku = self._ichimoku_cloud(highs, lows, closes)
        
        # Volume analysis
        volume_analysis = self._volume_analysis(closes, volumes)
        
        # Divergence detection
        divergences = self._detect_divergences(closes, indicators)
        
        # Oscillator confluence
        confluence = self._oscillator_confluence(indicators)
        
        # Generate signals from each strategy
        signals = self._generate_signals(
            closes, indicators, sr_levels, patterns, ichimoku, 
            divergences, confluence, mtf_trend
        )
        
        # Overall recommendation
        recommendation = self._aggregate_signals(signals)
        
        current_price = closes[-1]
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "current_price": round(current_price, 2),
            "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "indicators": indicators,
            "multi_timeframe_trend": mtf_trend,
            "support_resistance": sr_levels,
            "fibonacci_levels": fib_levels,
            "chart_patterns": patterns,
            "ichimoku": ichimoku,
            "volume_analysis": volume_analysis,
            "divergences": divergences,
            "oscillator_confluence": confluence,
            "signals": signals,
            "recommendation": recommendation,
            "trade_setup": self._trade_setup(
                current_price, sr_levels, fib_levels, recommendation
            ),
        }
    
    async def multi_asset_screening(
        self, symbols: list[str]
    ) -> dict[str, Any]:
        """Screen multiple assets for technical setups."""
        logger.info("[%s] Screening %d symbols", self.name, len(symbols))
        
        results = []
        for sym in symbols:
            analysis = await self.analyze(sym)
            if "error" not in analysis:
                results.append({
                    "symbol": sym,
                    "recommendation": analysis["recommendation"]["action"],
                    "confidence": analysis["recommendation"]["confidence"],
                    "trend": analysis["multi_timeframe_trend"]["overall"],
                    "patterns": [p["pattern"] for p in analysis["chart_patterns"][:3]],
                    "confluence_score": analysis["oscillator_confluence"]["score"],
                })
        
        # Sort by confluence score
        results.sort(key=lambda x: x["confluence_score"], reverse=True)
        
        # Filter by action
        buys = [r for r in results if r["recommendation"] in ["BUY", "STRONG_BUY"]]
        sells = [r for r in results if r["recommendation"] in ["SELL", "STRONG_SELL"]]
        
        return {
            "screened": len(results),
            "buy_signals": buys[:5],
            "sell_signals": sells[:5],
            "top_confluence": results[:5],
            "all_results": results,
        }
    
    async def _fetch_data(
        self, symbol: str, timeframe: str
    ) -> list[dict] | None:
        """Fetch OHLCV data based on timeframe."""
        def _fetch():
            ticker = yf.Ticker(symbol)
            
            if timeframe == "intraday":
                df = ticker.history(period="5d", interval="1h")
            elif timeframe == "weekly":
                df = ticker.history(period="5y", interval="1wk")
            else:  # daily
                df = ticker.history(period="2y", interval="1d")
            
            if df.empty:
                return None
            
            data = []
            for idx, row in df.iterrows():
                data.append({
                    "date": idx.strftime("%Y-%m-%d %H:%M"),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]),
                })
            
            return data
        
        return await asyncio.to_thread(_fetch)
    
    def _calculate_indicators(
        self,
        closes: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        volumes: np.ndarray,
    ) -> dict[str, Any]:
        """Calculate comprehensive technical indicators."""
        # Moving averages
        ma20 = self._sma(closes, 20)
        ma50 = self._sma(closes, 50)
        ma200 = self._sma(closes, 200)
        ema12 = self._ema(closes, 12)
        ema26 = self._ema(closes, 26)
        
        # MACD
        macd = ema12 - ema26
        macd_signal = self._ema(macd, 9)
        macd_hist = macd - macd_signal
        
        # RSI
        rsi = self._rsi(closes, 14)
        
        # Stochastic
        stoch_k, stoch_d = self._stochastic(highs, lows, closes)
        
        # ADX
        adx, plus_di, minus_di = self._adx(highs, lows, closes)
        
        # ATR
        atr = self._atr(highs, lows, closes)
        
        # Bollinger Bands
        bb_upper, bb_middle, bb_lower = self._bollinger_bands(closes)
        
        # CCI
        cci = self._cci(highs, lows, closes)
        
        # Williams %R
        williams_r = self._williams_r(highs, lows, closes)
        
        # OBV
        obv = self._obv(closes, volumes)
        
        return {
            "ma20": round(ma20[-1], 2),
            "ma50": round(ma50[-1], 2),
            "ma200": round(ma200[-1], 2) if len(ma200) > 0 and not np.isnan(ma200[-1]) else None,
            "ema12": round(ema12[-1], 2),
            "ema26": round(ema26[-1], 2),
            "macd": round(macd[-1], 4),
            "macd_signal": round(macd_signal[-1], 4),
            "macd_histogram": round(macd_hist[-1], 4),
            "rsi": round(rsi[-1], 2),
            "stoch_k": round(stoch_k[-1], 2),
            "stoch_d": round(stoch_d[-1], 2),
            "adx": round(adx[-1], 2),
            "plus_di": round(plus_di[-1], 2),
            "minus_di": round(minus_di[-1], 2),
            "atr": round(atr[-1], 2),
            "atr_pct": round(atr[-1] / closes[-1] * 100, 2),
            "bb_upper": round(bb_upper[-1], 2),
            "bb_middle": round(bb_middle[-1], 2),
            "bb_lower": round(bb_lower[-1], 2),
            "bb_width": round((bb_upper[-1] - bb_lower[-1]) / bb_middle[-1] * 100, 2),
            "bb_position": round((closes[-1] - bb_lower[-1]) / (bb_upper[-1] - bb_lower[-1]) * 100, 2),
            "cci": round(cci[-1], 2),
            "williams_r": round(williams_r[-1], 2),
            "obv_trend": "rising" if obv[-1] > obv[-20] else "falling",
        }
    
    def _multi_timeframe_trend(self, closes: np.ndarray) -> dict[str, Any]:
        """Analyze trend across multiple timeframes."""
        trends = {}
        
        # Short-term (5-20 days)
        if len(closes) >= 20:
            short_ma = self._sma(closes, 5)
            medium_ma = self._sma(closes, 20)
            trends["short_term"] = "bullish" if short_ma[-1] > medium_ma[-1] else "bearish"
        
        # Medium-term (20-50 days)
        if len(closes) >= 50:
            ma20 = self._sma(closes, 20)
            ma50 = self._sma(closes, 50)
            trends["medium_term"] = "bullish" if ma20[-1] > ma50[-1] else "bearish"
        
        # Long-term (50-200 days)
        if len(closes) >= 200:
            ma50 = self._sma(closes, 50)
            ma200 = self._sma(closes, 200)
            trends["long_term"] = "bullish" if ma50[-1] > ma200[-1] else "bearish"
        else:
            trends["long_term"] = "insufficient_data"
        
        # Price position
        if len(closes) >= 200:
            trends["price_vs_200ma"] = "above" if closes[-1] > self._sma(closes, 200)[-1] else "below"
        
        # Overall trend alignment
        bullish_count = sum(1 for t in trends.values() if t == "bullish" or t == "above")
        bearish_count = sum(1 for t in trends.values() if t == "bearish" or t == "below")
        
        if bullish_count >= 3:
            overall = "strong_bullish"
        elif bullish_count == 2:
            overall = "bullish"
        elif bearish_count >= 3:
            overall = "strong_bearish"
        elif bearish_count == 2:
            overall = "bearish"
        else:
            overall = "mixed"
        
        trends["overall"] = overall
        trends["alignment_score"] = bullish_count - bearish_count
        
        return trends
    
    def _support_resistance(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        lookback: int = 50,
    ) -> dict[str, Any]:
        """Detect support and resistance levels."""
        current = closes[-1]
        
        # Find pivot points
        pivots_high = []
        pivots_low = []
        
        for i in range(2, min(lookback, len(highs) - 2)):
            # Local high
            if highs[-i] > highs[-i-1] and highs[-i] > highs[-i+1] and \
               highs[-i] > highs[-i-2] and highs[-i] > highs[-i+2]:
                pivots_high.append(highs[-i])
            
            # Local low
            if lows[-i] < lows[-i-1] and lows[-i] < lows[-i+1] and \
               lows[-i] < lows[-i-2] and lows[-i] < lows[-i+2]:
                pivots_low.append(lows[-i])
        
        # Cluster nearby levels
        resistance_levels = self._cluster_levels(pivots_high, current)
        support_levels = self._cluster_levels(pivots_low, current)
        
        # Filter levels above/below current price
        resistances = sorted([r for r in resistance_levels if r > current])[:3]
        supports = sorted([s for s in support_levels if s < current], reverse=True)[:3]
        
        # Strength calculation based on number of touches
        nearest_resistance = resistances[0] if resistances else None
        nearest_support = supports[0] if supports else None
        
        return {
            "resistances": [round(r, 2) for r in resistances],
            "supports": [round(s, 2) for s in supports],
            "nearest_resistance": round(nearest_resistance, 2) if nearest_resistance else None,
            "nearest_support": round(nearest_support, 2) if nearest_support else None,
            "distance_to_resistance_pct": round((nearest_resistance - current) / current * 100, 2) if nearest_resistance else None,
            "distance_to_support_pct": round((current - nearest_support) / current * 100, 2) if nearest_support else None,
        }
    
    def _cluster_levels(
        self, levels: list[float], current: float, tolerance: float = 0.02
    ) -> list[float]:
        """Cluster nearby price levels."""
        if not levels:
            return []
        
        levels = sorted(levels)
        clusters = []
        current_cluster = [levels[0]]
        
        for level in levels[1:]:
            if (level - current_cluster[0]) / current_cluster[0] < tolerance:
                current_cluster.append(level)
            else:
                clusters.append(np.mean(current_cluster))
                current_cluster = [level]
        
        clusters.append(np.mean(current_cluster))
        return clusters
    
    def _fibonacci_levels(
        self, highs: np.ndarray, lows: np.ndarray, lookback: int = 100
    ) -> dict[str, Any]:
        """Calculate Fibonacci retracement levels."""
        high = np.max(highs[-lookback:])
        low = np.min(lows[-lookback:])
        diff = high - low
        
        # Retracement levels from high
        levels = {
            "0.0": round(high, 2),
            "0.236": round(high - 0.236 * diff, 2),
            "0.382": round(high - 0.382 * diff, 2),
            "0.5": round(high - 0.5 * diff, 2),
            "0.618": round(high - 0.618 * diff, 2),
            "0.786": round(high - 0.786 * diff, 2),
            "1.0": round(low, 2),
        }
        
        # Extension levels
        extensions = {
            "1.272": round(high + 0.272 * diff, 2),
            "1.618": round(high + 0.618 * diff, 2),
            "2.618": round(high + 1.618 * diff, 2),
        }
        
        return {
            "swing_high": round(high, 2),
            "swing_low": round(low, 2),
            "retracement_levels": levels,
            "extension_levels": extensions,
        }
    
    def _detect_patterns(
        self,
        closes: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        volumes: np.ndarray,
    ) -> list[dict]:
        """Detect chart patterns."""
        patterns = []
        
        # Double top/bottom
        if len(closes) >= 50:
            dt = self._detect_double_top(highs, closes)
            if dt:
                patterns.append(dt)
            
            db = self._detect_double_bottom(lows, closes)
            if db:
                patterns.append(db)
        
        # Head and shoulders
        hs = self._detect_head_shoulders(highs, closes)
        if hs:
            patterns.append(hs)
        
        # Flags and pennants
        flag = self._detect_flag(closes, volumes)
        if flag:
            patterns.append(flag)
        
        # Wedges
        wedge = self._detect_wedge(highs, lows)
        if wedge:
            patterns.append(wedge)
        
        # Candlestick patterns (last few candles)
        candle_patterns = self._detect_candlestick_patterns(
            closes[-10:], highs[-10:], lows[-10:], 
            np.array([closes[-11]] if len(closes) > 10 else [closes[0]])
        )
        patterns.extend(candle_patterns)
        
        return patterns
    
    def _detect_double_top(
        self, highs: np.ndarray, closes: np.ndarray
    ) -> dict | None:
        """Detect double top pattern."""
        lookback = 50
        if len(highs) < lookback:
            return None
        
        recent_highs = highs[-lookback:]
        
        # Find two peaks that are within 2% of each other
        peaks = []
        for i in range(2, len(recent_highs) - 2):
            if recent_highs[i] > recent_highs[i-1] and recent_highs[i] > recent_highs[i+1]:
                if recent_highs[i] > recent_highs[i-2] and recent_highs[i] > recent_highs[i+2]:
                    peaks.append((i, recent_highs[i]))
        
        if len(peaks) >= 2:
            # Check last two peaks
            peak1, peak2 = peaks[-2], peaks[-1]
            if abs(peak1[1] - peak2[1]) / peak1[1] < 0.02:
                # Peaks are similar height
                if peak2[0] - peak1[0] >= 10:  # At least 10 bars apart
                    return {
                        "pattern": "DOUBLE_TOP",
                        "type": "bearish",
                        "strength": 0.7,
                        "peak_prices": [round(peak1[1], 2), round(peak2[1], 2)],
                        "signal": "SELL",
                    }
        
        return None
    
    def _detect_double_bottom(
        self, lows: np.ndarray, closes: np.ndarray
    ) -> dict | None:
        """Detect double bottom pattern."""
        lookback = 50
        if len(lows) < lookback:
            return None
        
        recent_lows = lows[-lookback:]
        
        troughs = []
        for i in range(2, len(recent_lows) - 2):
            if recent_lows[i] < recent_lows[i-1] and recent_lows[i] < recent_lows[i+1]:
                if recent_lows[i] < recent_lows[i-2] and recent_lows[i] < recent_lows[i+2]:
                    troughs.append((i, recent_lows[i]))
        
        if len(troughs) >= 2:
            trough1, trough2 = troughs[-2], troughs[-1]
            if abs(trough1[1] - trough2[1]) / trough1[1] < 0.02:
                if trough2[0] - trough1[0] >= 10:
                    return {
                        "pattern": "DOUBLE_BOTTOM",
                        "type": "bullish",
                        "strength": 0.7,
                        "trough_prices": [round(trough1[1], 2), round(trough2[1], 2)],
                        "signal": "BUY",
                    }
        
        return None
    
    def _detect_head_shoulders(
        self, highs: np.ndarray, closes: np.ndarray
    ) -> dict | None:
        """Simplified head and shoulders detection."""
        if len(highs) < 60:
            return None
        
        # Look for three peaks where middle is highest
        recent = highs[-60:]
        peaks = []
        
        for i in range(3, len(recent) - 3):
            if recent[i] > max(recent[i-3:i]) and recent[i] > max(recent[i+1:i+4]):
                peaks.append((i, recent[i]))
        
        if len(peaks) >= 3:
            for i in range(len(peaks) - 2):
                left = peaks[i][1]
                head = peaks[i+1][1]
                right = peaks[i+2][1]
                
                # Head should be highest, shoulders similar height
                if head > left and head > right:
                    if abs(left - right) / left < 0.05:  # Shoulders within 5%
                        if head > left * 1.05:  # Head at least 5% higher
                            return {
                                "pattern": "HEAD_SHOULDERS",
                                "type": "bearish",
                                "strength": 0.8,
                                "signal": "SELL",
                            }
        
        return None
    
    def _detect_flag(
        self, closes: np.ndarray, volumes: np.ndarray
    ) -> dict | None:
        """Detect bull/bear flag pattern."""
        if len(closes) < 30:
            return None
        
        # Look for strong move followed by consolidation
        initial_move = (closes[-30] - closes[-20]) / closes[-30]
        consolidation_range = (max(closes[-10:]) - min(closes[-10:])) / closes[-10]
        
        if abs(initial_move) > 0.05 and consolidation_range < 0.03:
            flag_type = "BULL_FLAG" if initial_move > 0 else "BEAR_FLAG"
            signal = "BUY" if flag_type == "BULL_FLAG" else "SELL"
            
            return {
                "pattern": flag_type,
                "type": "continuation",
                "strength": 0.6,
                "signal": signal,
            }
        
        return None
    
    def _detect_wedge(
        self, highs: np.ndarray, lows: np.ndarray
    ) -> dict | None:
        """Detect rising/falling wedge."""
        if len(highs) < 30:
            return None
        
        # Simple linear regression of highs and lows
        x = np.arange(30)
        
        high_slope = np.polyfit(x, highs[-30:], 1)[0]
        low_slope = np.polyfit(x, lows[-30:], 1)[0]
        
        # Rising wedge: both slopes positive but converging
        if high_slope > 0 and low_slope > 0 and high_slope < low_slope:
            return {
                "pattern": "RISING_WEDGE",
                "type": "bearish",
                "strength": 0.65,
                "signal": "SELL",
            }
        
        # Falling wedge: both slopes negative but converging
        if high_slope < 0 and low_slope < 0 and abs(high_slope) < abs(low_slope):
            return {
                "pattern": "FALLING_WEDGE",
                "type": "bullish",
                "strength": 0.65,
                "signal": "BUY",
            }
        
        return None
    
    def _detect_candlestick_patterns(
        self,
        closes: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        prev_close: np.ndarray,
    ) -> list[dict]:
        """Detect common candlestick patterns."""
        patterns = []
        
        if len(closes) < 3:
            return patterns
        
        # Get last candle metrics
        open_price = prev_close[-1] if len(prev_close) > 0 else closes[-2]
        close = closes[-1]
        high = highs[-1]
        low = lows[-1]
        body = abs(close - open_price)
        range_size = high - low
        
        # Doji
        if body < range_size * 0.1:
            patterns.append({
                "pattern": "DOJI",
                "type": "neutral",
                "strength": 0.4,
                "signal": "HOLD",
            })
        
        # Hammer (small body at top, long lower wick)
        if body < range_size * 0.3 and (min(close, open_price) - low) > body * 2:
            patterns.append({
                "pattern": "HAMMER",
                "type": "bullish",
                "strength": 0.6,
                "signal": "BUY",
            })
        
        # Shooting star (small body at bottom, long upper wick)
        if body < range_size * 0.3 and (high - max(close, open_price)) > body * 2:
            patterns.append({
                "pattern": "SHOOTING_STAR",
                "type": "bearish",
                "strength": 0.6,
                "signal": "SELL",
            })
        
        # Engulfing patterns (need 2 candles)
        if len(closes) >= 2:
            prev_body = abs(closes[-2] - closes[-3]) if len(closes) >= 3 else abs(closes[-2] - closes[-1])
            
            # Bullish engulfing
            if close > open_price and body > prev_body * 1.5:
                patterns.append({
                    "pattern": "BULLISH_ENGULFING",
                    "type": "bullish",
                    "strength": 0.7,
                    "signal": "BUY",
                })
            
            # Bearish engulfing
            elif close < open_price and body > prev_body * 1.5:
                patterns.append({
                    "pattern": "BEARISH_ENGULFING",
                    "type": "bearish",
                    "strength": 0.7,
                    "signal": "SELL",
                })
        
        return patterns
    
    def _ichimoku_cloud(
        self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray
    ) -> dict[str, Any]:
        """Calculate Ichimoku Cloud indicators."""
        if len(closes) < 52:
            return {"status": "insufficient_data"}
        
        # Tenkan-sen (Conversion Line): (9-period high + 9-period low) / 2
        tenkan = (np.max(highs[-9:]) + np.min(lows[-9:])) / 2
        
        # Kijun-sen (Base Line): (26-period high + 26-period low) / 2
        kijun = (np.max(highs[-26:]) + np.min(lows[-26:])) / 2
        
        # Senkou Span A (Leading Span A): (Tenkan + Kijun) / 2
        senkou_a = (tenkan + kijun) / 2
        
        # Senkou Span B (Leading Span B): (52-period high + 52-period low) / 2
        senkou_b = (np.max(highs[-52:]) + np.min(lows[-52:])) / 2
        
        current = closes[-1]
        
        # Determine cloud position
        if current > max(senkou_a, senkou_b):
            cloud_position = "above_cloud"
            bias = "bullish"
        elif current < min(senkou_a, senkou_b):
            cloud_position = "below_cloud"
            bias = "bearish"
        else:
            cloud_position = "inside_cloud"
            bias = "neutral"
        
        # TK Cross
        if tenkan > kijun:
            tk_cross = "bullish"
        else:
            tk_cross = "bearish"
        
        # Cloud color
        cloud_color = "green" if senkou_a > senkou_b else "red"
        
        return {
            "tenkan_sen": round(tenkan, 2),
            "kijun_sen": round(kijun, 2),
            "senkou_span_a": round(senkou_a, 2),
            "senkou_span_b": round(senkou_b, 2),
            "cloud_position": cloud_position,
            "tk_cross": tk_cross,
            "cloud_color": cloud_color,
            "overall_bias": bias,
            "cloud_thickness": round(abs(senkou_a - senkou_b), 2),
        }
    
    def _volume_analysis(
        self, closes: np.ndarray, volumes: np.ndarray
    ) -> dict[str, Any]:
        """Analyze volume patterns."""
        avg_volume = np.mean(volumes[-20:])
        current_volume = volumes[-1]
        
        # Volume trend
        volume_ma5 = np.mean(volumes[-5:])
        volume_ma20 = np.mean(volumes[-20:])
        volume_trend = "increasing" if volume_ma5 > volume_ma20 else "decreasing"
        
        # Volume-price correlation
        price_changes = np.diff(closes[-20:])
        volume_changes = np.diff(volumes[-20:])
        
        if len(price_changes) > 0 and len(volume_changes) > 0:
            correlation = np.corrcoef(price_changes, volume_changes[:len(price_changes)])[0, 1]
        else:
            correlation = 0
        
        # Volume spike detection
        volume_spike = current_volume > avg_volume * 1.5
        
        return {
            "current_volume": int(current_volume),
            "avg_volume_20d": int(avg_volume),
            "volume_ratio": round(current_volume / avg_volume, 2) if avg_volume > 0 else 0,
            "volume_trend": volume_trend,
            "volume_spike": volume_spike,
            "price_volume_correlation": round(correlation, 3) if not np.isnan(correlation) else 0,
            "interpretation": self._interpret_volume(current_volume, avg_volume, closes[-1], closes[-2]),
        }
    
    def _interpret_volume(
        self, current_vol: float, avg_vol: float, current_price: float, prev_price: float
    ) -> str:
        """Interpret volume in context of price action."""
        vol_high = current_vol > avg_vol * 1.5
        price_up = current_price > prev_price
        
        if vol_high and price_up:
            return "Strong buying pressure - bullish"
        elif vol_high and not price_up:
            return "Strong selling pressure - bearish"
        elif not vol_high and price_up:
            return "Weak rally - caution"
        else:
            return "Low conviction selling"
    
    def _detect_divergences(
        self, closes: np.ndarray, indicators: dict
    ) -> list[dict]:
        """Detect price-indicator divergences."""
        divergences = []
        lookback = 20
        
        if len(closes) < lookback:
            return divergences
        
        # Price trend
        price_trend = closes[-1] > closes[-lookback]
        
        # RSI divergence
        rsi = indicators.get("rsi", 50)
        
        # Simplified: compare current vs historical high/low
        if price_trend and rsi < 50:
            divergences.append({
                "type": "BEARISH_DIVERGENCE",
                "indicator": "RSI",
                "description": "Price making higher highs but RSI not confirming",
                "signal": "SELL",
                "strength": 0.6,
            })
        
        if not price_trend and rsi > 50:
            divergences.append({
                "type": "BULLISH_DIVERGENCE",
                "indicator": "RSI",
                "description": "Price making lower lows but RSI not confirming",
                "signal": "BUY",
                "strength": 0.6,
            })
        
        # MACD histogram divergence
        macd_hist = indicators.get("macd_histogram", 0)
        
        if price_trend and macd_hist < 0:
            divergences.append({
                "type": "BEARISH_DIVERGENCE",
                "indicator": "MACD",
                "description": "Price rising but MACD histogram negative",
                "signal": "SELL",
                "strength": 0.5,
            })
        
        if not price_trend and macd_hist > 0:
            divergences.append({
                "type": "BULLISH_DIVERGENCE",
                "indicator": "MACD",
                "description": "Price falling but MACD histogram positive",
                "signal": "BUY",
                "strength": 0.5,
            })
        
        return divergences
    
    def _oscillator_confluence(self, indicators: dict) -> dict[str, Any]:
        """Calculate oscillator confluence score."""
        bullish_signals = 0
        bearish_signals = 0
        total_signals = 0
        
        # RSI
        rsi = indicators.get("rsi", 50)
        if rsi < 30:
            bullish_signals += 1
        elif rsi > 70:
            bearish_signals += 1
        total_signals += 1
        
        # Stochastic
        stoch_k = indicators.get("stoch_k", 50)
        if stoch_k < 20:
            bullish_signals += 1
        elif stoch_k > 80:
            bearish_signals += 1
        total_signals += 1
        
        # MACD
        macd = indicators.get("macd", 0)
        macd_signal = indicators.get("macd_signal", 0)
        if macd > macd_signal:
            bullish_signals += 1
        else:
            bearish_signals += 1
        total_signals += 1
        
        # CCI
        cci = indicators.get("cci", 0)
        if cci < -100:
            bullish_signals += 1
        elif cci > 100:
            bearish_signals += 1
        total_signals += 1
        
        # Williams %R
        williams = indicators.get("williams_r", -50)
        if williams < -80:
            bullish_signals += 1
        elif williams > -20:
            bearish_signals += 1
        total_signals += 1
        
        # ADX trend strength
        adx = indicators.get("adx", 25)
        plus_di = indicators.get("plus_di", 25)
        minus_di = indicators.get("minus_di", 25)
        
        if adx > 25:
            if plus_di > minus_di:
                bullish_signals += 1
            else:
                bearish_signals += 1
        total_signals += 1
        
        # Calculate score
        if bullish_signals > bearish_signals:
            score = (bullish_signals / total_signals) * 100
            bias = "bullish"
        elif bearish_signals > bullish_signals:
            score = (bearish_signals / total_signals) * 100
            bias = "bearish"
        else:
            score = 50
            bias = "neutral"
        
        return {
            "score": round(score, 1),
            "bias": bias,
            "bullish_signals": bullish_signals,
            "bearish_signals": bearish_signals,
            "total_checked": total_signals,
            "strength": "strong" if score > 70 else "moderate" if score > 50 else "weak",
        }
    
    def _generate_signals(
        self,
        closes: np.ndarray,
        indicators: dict,
        sr_levels: dict,
        patterns: list,
        ichimoku: dict,
        divergences: list,
        confluence: dict,
        mtf_trend: dict,
    ) -> list[dict]:
        """Generate trading signals from all analysis."""
        signals = []
        current = closes[-1]
        
        # Trend following signals
        if mtf_trend.get("overall") in ["strong_bullish", "bullish"]:
            signals.append({
                "strategy": "TREND_FOLLOWING",
                "signal": "BUY",
                "strength": 0.7 if mtf_trend["overall"] == "strong_bullish" else 0.5,
                "reason": f"Multi-timeframe trend is {mtf_trend['overall']}",
            })
        elif mtf_trend.get("overall") in ["strong_bearish", "bearish"]:
            signals.append({
                "strategy": "TREND_FOLLOWING",
                "signal": "SELL",
                "strength": 0.7 if mtf_trend["overall"] == "strong_bearish" else 0.5,
                "reason": f"Multi-timeframe trend is {mtf_trend['overall']}",
            })
        
        # Mean reversion from oscillators
        if confluence["bias"] == "bullish" and confluence["score"] > 60:
            signals.append({
                "strategy": "MEAN_REVERSION",
                "signal": "BUY",
                "strength": confluence["score"] / 100,
                "reason": f"Oscillator confluence score: {confluence['score']}% bullish",
            })
        elif confluence["bias"] == "bearish" and confluence["score"] > 60:
            signals.append({
                "strategy": "MEAN_REVERSION",
                "signal": "SELL",
                "strength": confluence["score"] / 100,
                "reason": f"Oscillator confluence score: {confluence['score']}% bearish",
            })
        
        # Pattern signals
        for pattern in patterns:
            if pattern.get("signal"):
                signals.append({
                    "strategy": "PATTERN",
                    "signal": pattern["signal"],
                    "strength": pattern.get("strength", 0.5),
                    "reason": f"{pattern['pattern']} pattern detected - {pattern['type']}",
                })
        
        # Ichimoku signals
        if ichimoku.get("status") != "insufficient_data":
            if ichimoku["overall_bias"] == "bullish" and ichimoku["tk_cross"] == "bullish":
                signals.append({
                    "strategy": "ICHIMOKU",
                    "signal": "BUY",
                    "strength": 0.65,
                    "reason": "Price above cloud with bullish TK cross",
                })
            elif ichimoku["overall_bias"] == "bearish" and ichimoku["tk_cross"] == "bearish":
                signals.append({
                    "strategy": "ICHIMOKU",
                    "signal": "SELL",
                    "strength": 0.65,
                    "reason": "Price below cloud with bearish TK cross",
                })
        
        # Divergence signals
        for div in divergences:
            signals.append({
                "strategy": "DIVERGENCE",
                "signal": div["signal"],
                "strength": div["strength"],
                "reason": div["description"],
            })
        
        # Support/Resistance breakout
        if sr_levels.get("nearest_resistance"):
            dist_to_res = sr_levels["distance_to_resistance_pct"]
            if dist_to_res and dist_to_res < 2:
                signals.append({
                    "strategy": "BREAKOUT",
                    "signal": "WATCH",
                    "strength": 0.4,
                    "reason": f"Approaching resistance at {sr_levels['nearest_resistance']}",
                })
        
        if sr_levels.get("nearest_support"):
            dist_to_sup = sr_levels["distance_to_support_pct"]
            if dist_to_sup and dist_to_sup < 2:
                signals.append({
                    "strategy": "SUPPORT",
                    "signal": "BUY",
                    "strength": 0.5,
                    "reason": f"Near support at {sr_levels['nearest_support']}",
                })
        
        return signals
    
    def _aggregate_signals(self, signals: list[dict]) -> dict[str, Any]:
        """Aggregate all signals into final recommendation."""
        if not signals:
            return {"action": "HOLD", "confidence": 0.3, "reason": "No clear signals"}
        
        buy_score = sum(
            s["strength"] for s in signals if s["signal"] in ["BUY", "STRONG_BUY"]
        )
        sell_score = sum(
            s["strength"] for s in signals if s["signal"] in ["SELL", "STRONG_SELL"]
        )
        
        buy_count = len([s for s in signals if s["signal"] in ["BUY", "STRONG_BUY"]])
        sell_count = len([s for s in signals if s["signal"] in ["SELL", "STRONG_SELL"]])
        
        if buy_score > sell_score * 1.5 and buy_count >= 2:
            action = "STRONG_BUY" if buy_score > 2.5 else "BUY"
            confidence = min(buy_score / 3, 0.9)
        elif sell_score > buy_score * 1.5 and sell_count >= 2:
            action = "STRONG_SELL" if sell_score > 2.5 else "SELL"
            confidence = min(sell_score / 3, 0.9)
        elif buy_score > sell_score:
            action = "WEAK_BUY"
            confidence = 0.4 + (buy_score - sell_score) / 5
        elif sell_score > buy_score:
            action = "WEAK_SELL"
            confidence = 0.4 + (sell_score - buy_score) / 5
        else:
            action = "HOLD"
            confidence = 0.3
        
        # Generate reason
        top_buy = [s for s in signals if s["signal"] in ["BUY", "STRONG_BUY"]]
        top_sell = [s for s in signals if s["signal"] in ["SELL", "STRONG_SELL"]]
        
        if action in ["BUY", "STRONG_BUY", "WEAK_BUY"]:
            reasons = [s["reason"] for s in sorted(top_buy, key=lambda x: -x["strength"])[:2]]
        elif action in ["SELL", "STRONG_SELL", "WEAK_SELL"]:
            reasons = [s["reason"] for s in sorted(top_sell, key=lambda x: -x["strength"])[:2]]
        else:
            reasons = ["Mixed signals - no clear direction"]
        
        return {
            "action": action,
            "confidence": round(confidence, 2),
            "buy_signals": buy_count,
            "sell_signals": sell_count,
            "buy_score": round(buy_score, 2),
            "sell_score": round(sell_score, 2),
            "reasons": reasons,
        }
    
    def _trade_setup(
        self,
        current_price: float,
        sr_levels: dict,
        fib_levels: dict,
        recommendation: dict,
    ) -> dict[str, Any]:
        """Generate trade setup based on analysis."""
        action = recommendation["action"]
        
        if action in ["HOLD", "WEAK_BUY", "WEAK_SELL"]:
            return {"setup": "NO_TRADE", "reason": "Signal not strong enough"}
        
        # Entry
        entry = current_price
        
        # Stop loss - nearest support or 2 ATR
        if action in ["BUY", "STRONG_BUY"]:
            stop = sr_levels.get("nearest_support")
            if not stop:
                stop = current_price * 0.95  # 5% default
            target = sr_levels.get("nearest_resistance")
            if not target:
                target = current_price * 1.10  # 10% default
        else:
            stop = sr_levels.get("nearest_resistance")
            if not stop:
                stop = current_price * 1.05
            target = sr_levels.get("nearest_support")
            if not target:
                target = current_price * 0.90
        
        risk = abs(entry - stop)
        reward = abs(target - entry)
        rr_ratio = reward / risk if risk > 0 else 0
        
        return {
            "setup": "ACTIVE",
            "action": action,
            "entry_price": round(entry, 2),
            "stop_loss": round(stop, 2),
            "target_price": round(target, 2),
            "risk_pct": round(abs(entry - stop) / entry * 100, 2),
            "reward_pct": round(abs(target - entry) / entry * 100, 2),
            "risk_reward_ratio": round(rr_ratio, 2),
            "position_valid": rr_ratio >= 1.5,
        }
    
    # Helper functions
    def _sma(self, data: np.ndarray, period: int) -> np.ndarray:
        """Simple moving average."""
        if len(data) < period:
            return np.full(len(data), np.nan)
        return np.convolve(data, np.ones(period)/period, mode='valid')
    
    def _ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """Exponential moving average."""
        multiplier = 2 / (period + 1)
        ema = np.zeros(len(data))
        ema[0] = data[0]
        for i in range(1, len(data)):
            ema[i] = (data[i] - ema[i-1]) * multiplier + ema[i-1]
        return ema
    
    def _rsi(self, prices: np.ndarray, period: int = 14) -> np.ndarray:
        """Relative Strength Index."""
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.zeros(len(prices))
        avg_loss = np.zeros(len(prices))
        rsi = np.full(len(prices), 50.0)
        
        # Initial average
        if len(gains) >= period:
            avg_gain[period] = np.mean(gains[:period])
            avg_loss[period] = np.mean(losses[:period])
            
            for i in range(period + 1, len(prices)):
                avg_gain[i] = (avg_gain[i-1] * (period - 1) + gains[i-1]) / period
                avg_loss[i] = (avg_loss[i-1] * (period - 1) + losses[i-1]) / period
                
                if avg_loss[i] == 0:
                    rsi[i] = 100
                else:
                    rs = avg_gain[i] / avg_loss[i]
                    rsi[i] = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _stochastic(
        self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, k_period: int = 14, d_period: int = 3
    ) -> tuple[np.ndarray, np.ndarray]:
        """Stochastic oscillator."""
        k = np.zeros(len(closes))
        
        for i in range(k_period - 1, len(closes)):
            low_min = np.min(lows[i - k_period + 1:i + 1])
            high_max = np.max(highs[i - k_period + 1:i + 1])
            if high_max - low_min > 0:
                k[i] = 100 * (closes[i] - low_min) / (high_max - low_min)
            else:
                k[i] = 50
        
        d = self._sma(k, d_period)
        d = np.concatenate([np.full(d_period - 1, np.nan), d])
        
        return k, d
    
    def _adx(
        self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Average Directional Index."""
        tr = np.maximum(
            highs[1:] - lows[1:],
            np.maximum(
                np.abs(highs[1:] - closes[:-1]),
                np.abs(lows[1:] - closes[:-1])
            )
        )
        
        plus_dm = np.zeros(len(tr))
        minus_dm = np.zeros(len(tr))
        
        for i in range(len(tr)):
            up_move = highs[i + 1] - highs[i]
            down_move = lows[i] - lows[i + 1]
            
            if up_move > down_move and up_move > 0:
                plus_dm[i] = up_move
            if down_move > up_move and down_move > 0:
                minus_dm[i] = down_move
        
        atr = self._ema(tr, period)
        plus_di = 100 * self._ema(plus_dm, period) / (atr + 1e-10)
        minus_di = 100 * self._ema(minus_dm, period) / (atr + 1e-10)
        
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        adx = self._ema(dx, period)
        
        # Pad to original length
        padding = len(closes) - len(adx)
        adx = np.concatenate([np.full(padding, np.nan), adx])
        plus_di = np.concatenate([np.full(padding, np.nan), plus_di])
        minus_di = np.concatenate([np.full(padding, np.nan), minus_di])
        
        return adx, plus_di, minus_di
    
    def _atr(
        self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14
    ) -> np.ndarray:
        """Average True Range."""
        tr = np.maximum(
            highs[1:] - lows[1:],
            np.maximum(
                np.abs(highs[1:] - closes[:-1]),
                np.abs(lows[1:] - closes[:-1])
            )
        )
        atr = self._ema(tr, period)
        return np.concatenate([[atr[0]], atr])
    
    def _bollinger_bands(
        self, closes: np.ndarray, period: int = 20, num_std: float = 2.0
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Bollinger Bands."""
        middle = self._sma(closes, period)
        middle = np.concatenate([np.full(period - 1, np.nan), middle])
        
        std = np.zeros(len(closes))
        for i in range(period - 1, len(closes)):
            std[i] = np.std(closes[i - period + 1:i + 1])
        
        upper = middle + num_std * std
        lower = middle - num_std * std
        
        return upper, middle, lower
    
    def _cci(
        self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 20
    ) -> np.ndarray:
        """Commodity Channel Index."""
        tp = (highs + lows + closes) / 3
        sma_tp = self._sma(tp, period)
        sma_tp = np.concatenate([np.full(period - 1, np.nan), sma_tp])
        
        mean_dev = np.zeros(len(tp))
        for i in range(period - 1, len(tp)):
            mean_dev[i] = np.mean(np.abs(tp[i - period + 1:i + 1] - sma_tp[i]))
        
        cci = (tp - sma_tp) / (0.015 * mean_dev + 1e-10)
        return cci
    
    def _williams_r(
        self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14
    ) -> np.ndarray:
        """Williams %R."""
        wr = np.zeros(len(closes))
        
        for i in range(period - 1, len(closes)):
            high_max = np.max(highs[i - period + 1:i + 1])
            low_min = np.min(lows[i - period + 1:i + 1])
            if high_max - low_min > 0:
                wr[i] = -100 * (high_max - closes[i]) / (high_max - low_min)
            else:
                wr[i] = -50
        
        return wr
    
    def _obv(self, closes: np.ndarray, volumes: np.ndarray) -> np.ndarray:
        """On-Balance Volume."""
        obv = np.zeros(len(closes))
        obv[0] = volumes[0]
        
        for i in range(1, len(closes)):
            if closes[i] > closes[i - 1]:
                obv[i] = obv[i - 1] + volumes[i]
            elif closes[i] < closes[i - 1]:
                obv[i] = obv[i - 1] - volumes[i]
            else:
                obv[i] = obv[i - 1]
        
        return obv
