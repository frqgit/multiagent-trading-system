"""Volatility Modeling Agent — Advanced volatility analysis and forecasting.

Implements:
- GARCH(1,1) volatility modeling
- Exponentially Weighted Moving Average (EWMA) volatility
- Parkinson (high-low) volatility
- Realized volatility computation
- Volatility regime detection
- VIX-based regime analysis
- Volatility term structure
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
class VolatilityMetrics:
    """Comprehensive volatility metrics."""
    historical_vol: float  # Standard realized volatility
    ewma_vol: float  # Exponentially weighted
    parkinson_vol: float  # High-low range based
    garch_vol: float  # GARCH(1,1) forecast
    current_regime: str  # low, normal, elevated, extreme
    regime_percentile: float  # Current vol percentile
    vol_of_vol: float  # Volatility of volatility
    vol_trend: str  # rising, falling, stable


class VolatilityModelingAgent:
    """
    Advanced volatility analysis and forecasting.
    
    Capabilities:
    - Multiple volatility estimators (historical, EWMA, Parkinson, GARCH)
    - Volatility regime detection with historical percentiles
    - Volatility forecasting
    - Volatility term structure analysis
    - Cross-asset volatility comparison
    """

    name = "VolatilityModelingAgent"
    
    # Regime thresholds (annualized volatility percentiles)
    REGIME_THRESHOLDS = {
        "low": 25,        # Below 25th percentile
        "normal": 50,     # 25th to 75th percentile
        "elevated": 85,   # 75th to 95th percentile
        "extreme": 100,   # Above 95th percentile
    }
    
    async def analyze(
        self,
        symbol: str,
        lookback_days: int = 252,
        forecast_horizon: int = 5,
    ) -> dict[str, Any]:
        """
        Comprehensive volatility analysis for a symbol.
        
        Args:
            symbol: Stock symbol
            lookback_days: Historical data lookback
            forecast_horizon: Days to forecast volatility
            
        Returns:
            Volatility analysis with multiple measures and forecasts
        """
        logger.info("[%s] Analyzing volatility for %s", self.name, symbol)
        
        # Fetch historical data
        try:
            data = await self._fetch_ohlcv(symbol, lookback_days)
        except Exception as e:
            logger.error("[%s] Failed to fetch data: %s", self.name, e)
            return {"error": f"Failed to fetch data: {e}", "symbol": symbol}
        
        if data is None or len(data) < 30:
            return {"error": "Insufficient data", "symbol": symbol}
        
        closes = np.array([d["close"] for d in data])
        highs = np.array([d["high"] for d in data])
        lows = np.array([d["low"] for d in data])
        
        # Calculate returns
        returns = np.diff(np.log(closes))
        
        # Calculate different volatility measures
        hist_vol = self._historical_volatility(returns)
        ewma_vol = self._ewma_volatility(returns)
        parkinson_vol = self._parkinson_volatility(highs, lows)
        garch_vol, garch_params = self._garch_volatility(returns, forecast_horizon)
        
        # Volatility regime detection
        regime, percentile = self._detect_regime(returns, lookback_days)
        
        # Volatility of volatility
        vol_of_vol = self._vol_of_vol(returns)
        
        # Vol trend (20-day vs 60-day)
        vol_trend = self._vol_trend(returns)
        
        # Volatility term structure (short vs long term)
        term_structure = self._volatility_term_structure(returns)
        
        # Intraday volatility estimate
        intraday_vol = self._intraday_volatility(data)
        
        # Historical percentiles
        percentile_history = self._volatility_percentile_history(returns)
        
        # Volatility forecast
        forecast = self._volatility_forecast(garch_params, returns, forecast_horizon)
        
        # Volatility-based trading signals
        signals = self._generate_vol_signals(
            hist_vol, percentile, vol_trend, garch_vol, ewma_vol
        )
        
        return {
            "symbol": symbol,
            "analysis_date": datetime.now().strftime("%Y-%m-%d"),
            "data_points": len(data),
            "volatility_measures": {
                "historical_20d": round(self._rolling_vol(returns, 20) * 100, 2),
                "historical_60d": round(self._rolling_vol(returns, 60) * 100, 2),
                "ewma": round(ewma_vol * 100, 2),
                "parkinson": round(parkinson_vol * 100, 2),
                "garch_forecast": round(garch_vol * 100, 2),
            },
            "annualized_historical": round(hist_vol * 100, 2),
            "regime": {
                "current": regime,
                "percentile": round(percentile, 1),
                "description": self._regime_description(regime),
            },
            "vol_of_vol": round(vol_of_vol * 100, 2),
            "vol_trend": vol_trend,
            "term_structure": term_structure,
            "intraday_volatility": round(intraday_vol * 100, 2),
            "garch_parameters": {
                "omega": round(garch_params["omega"], 8),
                "alpha": round(garch_params["alpha"], 4),
                "beta": round(garch_params["beta"], 4),
                "persistence": round(garch_params["alpha"] + garch_params["beta"], 4),
            },
            "forecast": forecast,
            "percentile_history": percentile_history,
            "trading_signals": signals,
            "risk_assessment": self._risk_assessment(hist_vol, percentile, regime),
        }
    
    async def compare_volatility(
        self, symbols: list[str]
    ) -> dict[str, Any]:
        """Compare volatility across multiple assets."""
        logger.info("[%s] Comparing volatility for %s", self.name, symbols)
        
        results = []
        for sym in symbols:
            analysis = await self.analyze(sym, lookback_days=126)  # 6 months
            if "error" not in analysis:
                results.append({
                    "symbol": sym,
                    "historical_vol": analysis["annualized_historical"],
                    "regime": analysis["regime"]["current"],
                    "percentile": analysis["regime"]["percentile"],
                    "vol_trend": analysis["vol_trend"],
                    "garch_forecast": analysis["volatility_measures"]["garch_forecast"],
                })
        
        if not results:
            return {"error": "Could not analyze any symbols", "symbols": symbols}
        
        # Rank by volatility
        ranked = sorted(results, key=lambda x: x["historical_vol"])
        
        return {
            "symbols_analyzed": len(results),
            "comparison": results,
            "lowest_volatility": ranked[0]["symbol"],
            "highest_volatility": ranked[-1]["symbol"],
            "average_volatility": round(np.mean([r["historical_vol"] for r in results]), 2),
        }
    
    async def _fetch_ohlcv(self, symbol: str, days: int) -> list[dict] | None:
        """Fetch OHLCV data."""
        def _fetch():
            ticker = yf.Ticker(symbol)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=int(days * 1.5))  # Extra buffer
            
            df = ticker.history(start=start_date, end=end_date, auto_adjust=True)
            
            if df.empty:
                return None
            
            data = []
            for idx, row in df.iterrows():
                data.append({
                    "date": idx.strftime("%Y-%m-%d"),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]),
                })
            
            return data[-days:] if len(data) > days else data
        
        return await asyncio.to_thread(_fetch)
    
    def _historical_volatility(
        self, returns: np.ndarray, annualize: bool = True
    ) -> float:
        """Calculate standard historical volatility."""
        vol = np.std(returns)
        return vol * np.sqrt(252) if annualize else vol
    
    def _rolling_vol(
        self, returns: np.ndarray, window: int, annualize: bool = True
    ) -> float:
        """Calculate rolling volatility for the last N days."""
        if len(returns) < window:
            return self._historical_volatility(returns, annualize)
        
        vol = np.std(returns[-window:])
        return vol * np.sqrt(252) if annualize else vol
    
    def _ewma_volatility(
        self, returns: np.ndarray, lambda_param: float = 0.94
    ) -> float:
        """
        Calculate EWMA (RiskMetrics) volatility.
        Lambda = 0.94 is the J.P. Morgan standard.
        """
        variance = returns[0] ** 2
        
        for r in returns[1:]:
            variance = lambda_param * variance + (1 - lambda_param) * (r ** 2)
        
        return np.sqrt(variance * 252)
    
    def _parkinson_volatility(
        self, highs: np.ndarray, lows: np.ndarray
    ) -> float:
        """
        Parkinson volatility estimator using high-low range.
        More efficient than close-to-close volatility.
        """
        log_hl_ratio = np.log(highs / lows)
        parkinson_factor = 1 / (4 * np.log(2))
        
        variance = parkinson_factor * np.mean(log_hl_ratio ** 2)
        return np.sqrt(variance * 252)
    
    def _garch_volatility(
        self, returns: np.ndarray, forecast_horizon: int = 5
    ) -> tuple[float, dict]:
        """
        Simplified GARCH(1,1) estimation and forecasting.
        
        σ²(t) = ω + α * r²(t-1) + β * σ²(t-1)
        
        Uses method of moments for quick estimation.
        """
        # Method of moments estimation
        sample_var = np.var(returns)
        autocorr = np.corrcoef(returns[1:]**2, returns[:-1]**2)[0, 1]
        
        # Typical GARCH parameters
        alpha = max(0.05, min(0.15, autocorr * 0.3))
        beta = max(0.75, min(0.92, 0.95 - alpha))
        omega = sample_var * (1 - alpha - beta)
        
        garch_params = {"omega": omega, "alpha": alpha, "beta": beta}
        
        # Calculate current GARCH variance
        variance = omega / (1 - alpha - beta)  # Long-run variance
        
        # Refine with recent returns
        for r in returns[-20:]:
            variance = omega + alpha * (r ** 2) + beta * variance
        
        # Forecast
        forecast_var = variance
        for _ in range(forecast_horizon):
            forecast_var = omega + (alpha + beta) * forecast_var
        
        return np.sqrt(forecast_var * 252), garch_params
    
    def _detect_regime(
        self, returns: np.ndarray, lookback: int
    ) -> tuple[str, float]:
        """
        Detect volatility regime based on historical percentiles.
        """
        # Calculate rolling volatility
        window = min(20, len(returns) // 5)
        current_vol = np.std(returns[-window:])
        
        # Historical distribution
        vol_history = []
        for i in range(window, len(returns)):
            vol_history.append(np.std(returns[i-window:i]))
        
        if not vol_history:
            return "normal", 50.0
        
        percentile = (np.sum(np.array(vol_history) < current_vol) / len(vol_history)) * 100
        
        if percentile < 25:
            regime = "low"
        elif percentile < 75:
            regime = "normal"
        elif percentile < 95:
            regime = "elevated"
        else:
            regime = "extreme"
        
        return regime, percentile
    
    def _vol_of_vol(self, returns: np.ndarray, window: int = 20) -> float:
        """Calculate volatility of volatility."""
        if len(returns) < window * 2:
            return 0.0
        
        vol_series = []
        for i in range(window, len(returns)):
            vol_series.append(np.std(returns[i-window:i]))
        
        return np.std(vol_series) * np.sqrt(252)
    
    def _vol_trend(self, returns: np.ndarray) -> str:
        """Determine if volatility is rising, falling, or stable."""
        if len(returns) < 60:
            return "insufficient_data"
        
        short_vol = np.std(returns[-20:])
        long_vol = np.std(returns[-60:])
        
        ratio = short_vol / long_vol if long_vol > 0 else 1.0
        
        if ratio > 1.15:
            return "rising"
        elif ratio < 0.85:
            return "falling"
        else:
            return "stable"
    
    def _volatility_term_structure(self, returns: np.ndarray) -> dict[str, Any]:
        """Analyze volatility term structure."""
        terms = {}
        
        if len(returns) >= 5:
            terms["5d"] = round(np.std(returns[-5:]) * np.sqrt(252) * 100, 2)
        if len(returns) >= 10:
            terms["10d"] = round(np.std(returns[-10:]) * np.sqrt(252) * 100, 2)
        if len(returns) >= 20:
            terms["20d"] = round(np.std(returns[-20:]) * np.sqrt(252) * 100, 2)
        if len(returns) >= 60:
            terms["60d"] = round(np.std(returns[-60:]) * np.sqrt(252) * 100, 2)
        if len(returns) >= 126:
            terms["126d"] = round(np.std(returns[-126:]) * np.sqrt(252) * 100, 2)
        if len(returns) >= 252:
            terms["252d"] = round(np.std(returns[-252:]) * np.sqrt(252) * 100, 2)
        
        # Term structure shape
        if len(terms) >= 2:
            values = list(terms.values())
            if values[0] > values[-1]:
                shape = "inverted"  # Short-term vol higher
            elif values[0] < values[-1]:
                shape = "contango"  # Long-term vol higher
            else:
                shape = "flat"
        else:
            shape = "insufficient_data"
        
        return {"levels": terms, "shape": shape}
    
    def _intraday_volatility(self, data: list[dict]) -> float:
        """Estimate average intraday volatility from high-low range."""
        if len(data) < 5:
            return 0.0
        
        ranges = [(d["high"] - d["low"]) / d["close"] for d in data[-20:]]
        return np.mean(ranges) * np.sqrt(252)
    
    def _volatility_percentile_history(
        self, returns: np.ndarray
    ) -> list[dict]:
        """Get historical percentile points."""
        if len(returns) < 20:
            return []
        
        current_vol = np.std(returns[-20:]) * np.sqrt(252)
        
        percentiles = [10, 25, 50, 75, 90, 95, 99]
        vol_history = []
        
        for i in range(20, len(returns)):
            vol_history.append(np.std(returns[i-20:i]) * np.sqrt(252))
        
        results = []
        for p in percentiles:
            level = np.percentile(vol_history, p) * 100
            results.append({"percentile": p, "volatility": round(level, 2)})
        
        return results
    
    def _volatility_forecast(
        self,
        garch_params: dict,
        returns: np.ndarray,
        horizon: int,
    ) -> list[dict]:
        """Generate volatility forecast."""
        omega = garch_params["omega"]
        alpha = garch_params["alpha"]
        beta = garch_params["beta"]
        
        # Current variance
        variance = omega / (1 - alpha - beta)
        for r in returns[-10:]:
            variance = omega + alpha * (r ** 2) + beta * variance
        
        # Forecast path
        forecasts = []
        for day in range(1, horizon + 1):
            variance = omega + (alpha + beta) * variance
            vol = np.sqrt(variance * 252)
            forecasts.append({
                "day": day,
                "forecast_vol": round(vol * 100, 2),
            })
        
        return forecasts
    
    def _generate_vol_signals(
        self,
        hist_vol: float,
        percentile: float,
        trend: str,
        garch_vol: float,
        ewma_vol: float,
    ) -> list[str]:
        """Generate trading signals based on volatility analysis."""
        signals = []
        
        # Low volatility regime
        if percentile < 20:
            signals.append("VOLATILITY_LOW: Consider volatility expansion strategies (straddles)")
            signals.append("VOLATILITY_LOW: Tighter stops may be appropriate")
        
        # High volatility regime
        elif percentile > 80:
            signals.append("VOLATILITY_HIGH: Reduce position sizes")
            signals.append("VOLATILITY_HIGH: Consider mean reversion strategies")
            if trend == "rising":
                signals.append("VOLATILITY_SPIKING: Exercise extreme caution")
        
        # Volatility compression
        if trend == "falling" and percentile > 50:
            signals.append("VOLATILITY_COMPRESSING: Potential breakout setup")
        
        # EWMA vs GARCH divergence
        if abs(garch_vol - ewma_vol) / ewma_vol > 0.15:
            if garch_vol > ewma_vol:
                signals.append("GARCH_RISING: Model expects higher vol ahead")
            else:
                signals.append("GARCH_FALLING: Model expects lower vol ahead")
        
        if not signals:
            signals.append("VOLATILITY_NORMAL: No special signals")
        
        return signals
    
    def _regime_description(self, regime: str) -> str:
        """Get human-readable regime description."""
        descriptions = {
            "low": "Market is calm with below-average volatility. Good for trend-following strategies.",
            "normal": "Volatility is within typical range. Standard position sizing appropriate.",
            "elevated": "Above-average volatility. Consider reducing position sizes and widening stops.",
            "extreme": "Extreme volatility conditions. High risk environment - use caution.",
        }
        return descriptions.get(regime, "Unknown volatility regime")
    
    def _risk_assessment(
        self, hist_vol: float, percentile: float, regime: str
    ) -> dict[str, Any]:
        """Comprehensive risk assessment based on volatility."""
        # Daily 1-sigma move
        daily_1sigma = hist_vol / np.sqrt(252)
        
        # Expected moves
        daily_2sigma = daily_1sigma * 2
        weekly_1sigma = hist_vol / np.sqrt(52)
        monthly_1sigma = hist_vol / np.sqrt(12)
        
        # Risk score (0-10)
        if regime == "extreme":
            risk_score = 10
        elif regime == "elevated":
            risk_score = 7
        elif regime == "normal":
            risk_score = 4
        else:
            risk_score = 2
        
        return {
            "risk_score": risk_score,
            "expected_daily_move": round(daily_1sigma * 100, 2),
            "expected_2sigma_daily": round(daily_2sigma * 100, 2),
            "expected_weekly_move": round(weekly_1sigma * 100, 2),
            "expected_monthly_move": round(monthly_1sigma * 100, 2),
            "position_size_recommendation": self._position_size_rec(percentile),
            "stop_loss_recommendation": f"Consider {round(daily_2sigma * 100 * 2, 1)}% stops",
        }
    
    def _position_size_rec(self, percentile: float) -> str:
        """Position sizing recommendation based on volatility percentile."""
        if percentile < 25:
            return "full_size"
        elif percentile < 50:
            return "standard_size"
        elif percentile < 75:
            return "75%_size"
        elif percentile < 90:
            return "50%_size"
        else:
            return "25%_size_or_avoid"
