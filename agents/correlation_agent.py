"""Correlation Analysis Agent — Cross-asset correlation and pair trading analysis.

Implements:
- Rolling correlation computation
- Correlation regime detection
- Pair trading signal generation
- Cointegration testing
- Beta and factor exposure analysis
- Correlation-based diversification scoring
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
class CorrelationPair:
    """Correlation between two assets."""
    symbol1: str
    symbol2: str
    correlation: float
    rolling_correlation: float
    correlation_change: float  # Short-term vs long-term
    cointegration_score: float
    pair_trade_signal: str | None
    z_score: float


class CorrelationAnalysisAgent:
    """
    Analyzes cross-asset correlations for portfolio construction and pair trading.
    
    Capabilities:
    - Full correlation matrix computation
    - Rolling correlation analysis
    - Correlation regime detection
    - Pair trading signals (mean reversion)
    - Cointegration testing
    - Beta calculation to market indices
    - Factor exposure analysis
    """

    name = "CorrelationAnalysisAgent"
    
    # Default market indices for beta calculation
    MARKET_INDICES = ["SPY", "QQQ", "IWM"]
    
    # Pair trading thresholds
    Z_SCORE_ENTRY = 2.0
    Z_SCORE_EXIT = 0.5
    
    async def analyze_correlations(
        self,
        symbols: list[str],
        lookback_days: int = 252,
    ) -> dict[str, Any]:
        """
        Compute full correlation matrix and analysis for given symbols.
        
        Args:
            symbols: List of stock symbols
            lookback_days: Historical lookback period
            
        Returns:
            Correlation matrix, regime analysis, and insights
        """
        logger.info("[%s] Analyzing correlations for %d symbols", self.name, len(symbols))
        
        if len(symbols) < 2:
            return {"error": "Need at least 2 symbols for correlation analysis"}
        
        # Fetch price data
        try:
            price_data = await self._fetch_prices(symbols, lookback_days)
        except Exception as e:
            return {"error": f"Failed to fetch data: {e}"}
        
        if len(price_data) < 2:
            return {"error": "Insufficient data for correlation analysis"}
        
        # Calculate returns
        returns_dict = {}
        valid_symbols = []
        
        for sym, prices in price_data.items():
            if len(prices) > 20:
                returns = np.diff(np.log(prices))
                returns_dict[sym] = returns
                valid_symbols.append(sym)
        
        if len(valid_symbols) < 2:
            return {"error": "Insufficient valid data"}
        
        # Align returns to common length
        min_len = min(len(r) for r in returns_dict.values())
        returns_matrix = np.array([returns_dict[s][-min_len:] for s in valid_symbols])
        
        # Full correlation matrix
        corr_matrix = np.corrcoef(returns_matrix)
        
        # Rolling correlations (20-day window)
        rolling_corrs = self._calculate_rolling_correlations(returns_matrix, valid_symbols, window=20)
        
        # Correlation regime
        regime = self._detect_correlation_regime(corr_matrix, returns_matrix, valid_symbols)
        
        # Pair analysis
        pairs = self._analyze_pairs(returns_matrix, valid_symbols)
        
        # Diversification metrics
        diversification = self._calculate_diversification_metrics(corr_matrix, valid_symbols)
        
        # Build readable correlation matrix
        readable_matrix = {}
        for i, s1 in enumerate(valid_symbols):
            readable_matrix[s1] = {}
            for j, s2 in enumerate(valid_symbols):
                readable_matrix[s1][s2] = round(corr_matrix[i, j], 3)
        
        # Find strongest and weakest correlations
        correlations_list = []
        for i in range(len(valid_symbols)):
            for j in range(i + 1, len(valid_symbols)):
                correlations_list.append({
                    "pair": f"{valid_symbols[i]}-{valid_symbols[j]}",
                    "correlation": round(corr_matrix[i, j], 3),
                })
        
        correlations_list.sort(key=lambda x: x["correlation"], reverse=True)
        
        return {
            "symbols_analyzed": valid_symbols,
            "data_points": min_len,
            "correlation_matrix": readable_matrix,
            "highest_correlations": correlations_list[:5],
            "lowest_correlations": correlations_list[-5:][::-1],
            "average_correlation": round(np.mean([c["correlation"] for c in correlations_list]), 3),
            "rolling_correlations": rolling_corrs,
            "regime": regime,
            "pair_trading_opportunities": pairs[:5],
            "diversification_metrics": diversification,
        }
    
    async def analyze_pair(
        self,
        symbol1: str,
        symbol2: str,
        lookback_days: int = 252,
    ) -> dict[str, Any]:
        """
        Deep analysis of a specific pair for pair trading.
        
        Args:
            symbol1: First symbol
            symbol2: Second symbol
            lookback_days: Historical lookback
            
        Returns:
            Detailed pair analysis with trading signals
        """
        logger.info("[%s] Analyzing pair: %s - %s", self.name, symbol1, symbol2)
        
        # Fetch data
        try:
            price_data = await self._fetch_prices([symbol1, symbol2], lookback_days)
        except Exception as e:
            return {"error": f"Failed to fetch data: {e}"}
        
        if symbol1 not in price_data or symbol2 not in price_data:
            return {"error": "Could not fetch data for one or both symbols"}
        
        prices1 = np.array(price_data[symbol1])
        prices2 = np.array(price_data[symbol2])
        
        # Align lengths
        min_len = min(len(prices1), len(prices2))
        prices1 = prices1[-min_len:]
        prices2 = prices2[-min_len:]
        
        # Calculate returns
        returns1 = np.diff(np.log(prices1))
        returns2 = np.diff(np.log(prices2))
        
        # Correlation analysis
        full_corr = np.corrcoef(returns1, returns2)[0, 1]
        
        # Rolling correlation
        window = 20
        rolling_corrs = []
        for i in range(window, len(returns1)):
            corr = np.corrcoef(returns1[i-window:i], returns2[i-window:i])[0, 1]
            rolling_corrs.append(corr)
        
        recent_corr = rolling_corrs[-1] if rolling_corrs else full_corr
        corr_change = recent_corr - np.mean(rolling_corrs) if rolling_corrs else 0
        
        # Cointegration test (simplified Engle-Granger)
        coint_score, hedge_ratio, residuals = self._cointegration_test(prices1, prices2)
        
        # Calculate spread statistics
        spread = np.log(prices1) - hedge_ratio * np.log(prices2)
        spread_mean = np.mean(spread)
        spread_std = np.std(spread)
        current_spread = spread[-1]
        z_score = (current_spread - spread_mean) / spread_std if spread_std > 0 else 0
        
        # Generate pair trading signal
        if z_score > self.Z_SCORE_ENTRY:
            signal = "SHORT_SPREAD"  # Short symbol1, Long symbol2
            signal_desc = f"Short {symbol1}, Long {symbol2}"
        elif z_score < -self.Z_SCORE_ENTRY:
            signal = "LONG_SPREAD"  # Long symbol1, Short symbol2
            signal_desc = f"Long {symbol1}, Short {symbol2}"
        elif abs(z_score) < self.Z_SCORE_EXIT:
            signal = "CLOSE_POSITION"
            signal_desc = "Close any existing position"
        else:
            signal = "NO_TRADE"
            signal_desc = "No signal"
        
        # Half-life of mean reversion
        half_life = self._calculate_half_life(spread)
        
        # Beta relationship
        beta = self._calculate_beta(returns1, returns2)
        
        return {
            "symbol1": symbol1,
            "symbol2": symbol2,
            "data_points": min_len,
            "correlation": {
                "full_period": round(full_corr, 3),
                "recent_20d": round(recent_corr, 3),
                "correlation_change": round(corr_change, 3),
                "rolling_correlations": [round(c, 3) for c in rolling_corrs[-30:]],
            },
            "cointegration": {
                "score": round(coint_score, 3),
                "hedge_ratio": round(hedge_ratio, 4),
                "is_cointegrated": coint_score < 0.05,
            },
            "spread_analysis": {
                "current_spread": round(current_spread, 4),
                "mean_spread": round(spread_mean, 4),
                "spread_std": round(spread_std, 4),
                "z_score": round(z_score, 3),
                "half_life_days": round(half_life, 1) if half_life else None,
            },
            "pair_trade": {
                "signal": signal,
                "description": signal_desc,
                "z_score": round(z_score, 3),
                "entry_threshold": self.Z_SCORE_ENTRY,
                "exit_threshold": self.Z_SCORE_EXIT,
            },
            "beta": {
                f"{symbol1}_to_{symbol2}": round(beta, 3),
            },
            "risk_metrics": {
                "spread_volatility": round(spread_std * np.sqrt(252), 4),
                "max_spread": round(np.max(spread), 4),
                "min_spread": round(np.min(spread), 4),
            },
        }
    
    async def calculate_betas(
        self,
        symbols: list[str],
        benchmark: str = "SPY",
        lookback_days: int = 252,
    ) -> dict[str, Any]:
        """
        Calculate beta exposure of symbols to a benchmark.
        
        Args:
            symbols: List of stock symbols
            benchmark: Benchmark index symbol
            lookback_days: Historical lookback
            
        Returns:
            Beta values and factor exposures
        """
        logger.info("[%s] Calculating betas for %d symbols vs %s", self.name, len(symbols), benchmark)
        
        all_symbols = symbols + [benchmark]
        
        try:
            price_data = await self._fetch_prices(all_symbols, lookback_days)
        except Exception as e:
            return {"error": f"Failed to fetch data: {e}"}
        
        if benchmark not in price_data:
            return {"error": f"Could not fetch benchmark {benchmark}"}
        
        benchmark_prices = np.array(price_data[benchmark])
        benchmark_returns = np.diff(np.log(benchmark_prices))
        
        results = []
        for sym in symbols:
            if sym not in price_data:
                continue
            
            prices = np.array(price_data[sym])
            min_len = min(len(prices), len(benchmark_prices))
            
            returns = np.diff(np.log(prices[-min_len:]))
            bench_ret = benchmark_returns[-min_len+1:]
            
            if len(returns) != len(bench_ret):
                min_len = min(len(returns), len(bench_ret))
                returns = returns[-min_len:]
                bench_ret = bench_ret[-min_len:]
            
            # Calculate beta
            covariance = np.cov(returns, bench_ret)[0, 1]
            variance = np.var(bench_ret)
            beta = covariance / variance if variance > 0 else 1.0
            
            # Calculate alpha (Jensen's alpha)
            expected_return = np.mean(returns) * 252
            benchmark_return = np.mean(bench_ret) * 252
            risk_free = 0.05  # 5% assumption
            alpha = expected_return - (risk_free + beta * (benchmark_return - risk_free))
            
            # Correlation to benchmark
            correlation = np.corrcoef(returns, bench_ret)[0, 1]
            
            # R-squared
            r_squared = correlation ** 2
            
            # Systematic vs idiosyncratic risk
            total_var = np.var(returns) * 252
            systematic_var = (beta ** 2) * (np.var(bench_ret) * 252)
            idio_var = total_var - systematic_var
            
            results.append({
                "symbol": sym,
                "beta": round(beta, 3),
                "alpha": round(alpha * 100, 2),  # As percentage
                "correlation": round(correlation, 3),
                "r_squared": round(r_squared, 3),
                "systematic_risk_pct": round(systematic_var / total_var * 100, 1) if total_var > 0 else 0,
                "idiosyncratic_risk_pct": round(idio_var / total_var * 100, 1) if total_var > 0 else 0,
                "category": self._categorize_beta(beta),
            })
        
        # Sort by beta
        results.sort(key=lambda x: x["beta"], reverse=True)
        
        # Portfolio beta (if equal weighted)
        avg_beta = np.mean([r["beta"] for r in results]) if results else 1.0
        
        return {
            "benchmark": benchmark,
            "results": results,
            "portfolio_beta": round(avg_beta, 3),
            "high_beta_stocks": [r["symbol"] for r in results if r["beta"] > 1.2][:5],
            "low_beta_stocks": [r["symbol"] for r in results if r["beta"] < 0.8][:5],
            "defensive_stocks": [r["symbol"] for r in results if r["beta"] < 0.5][:5],
        }
    
    async def _fetch_prices(
        self, symbols: list[str], days: int
    ) -> dict[str, list[float]]:
        """Fetch closing prices for symbols."""
        async def fetch_one(symbol: str) -> tuple[str, list[float]]:
            def _fetch():
                ticker = yf.Ticker(symbol)
                end_date = datetime.now()
                start_date = end_date - timedelta(days=int(days * 1.5))
                
                df = ticker.history(start=start_date, end=end_date, auto_adjust=True)
                
                if df.empty:
                    return (symbol, [])
                
                prices = df["Close"].tolist()
                return (symbol, prices[-days:] if len(prices) > days else prices)
            
            return await asyncio.to_thread(_fetch)
        
        results = await asyncio.gather(*[fetch_one(s) for s in symbols])
        return {sym: prices for sym, prices in results if prices}
    
    def _calculate_rolling_correlations(
        self,
        returns_matrix: np.ndarray,
        symbols: list[str],
        window: int = 20,
    ) -> list[dict]:
        """Calculate recent rolling correlations between pairs."""
        n_symbols = len(symbols)
        n_observations = returns_matrix.shape[1]
        
        if n_observations < window:
            return []
        
        rolling_corrs = []
        
        for i in range(n_symbols):
            for j in range(i + 1, n_symbols):
                recent = np.corrcoef(
                    returns_matrix[i, -window:],
                    returns_matrix[j, -window:]
                )[0, 1]
                
                historical = np.corrcoef(
                    returns_matrix[i, :-window],
                    returns_matrix[j, :-window]
                )[0, 1] if n_observations > window * 2 else recent
                
                rolling_corrs.append({
                    "pair": f"{symbols[i]}-{symbols[j]}",
                    "recent_correlation": round(recent, 3),
                    "historical_correlation": round(historical, 3),
                    "change": round(recent - historical, 3),
                    "trend": "increasing" if recent > historical else "decreasing",
                })
        
        # Sort by absolute change
        rolling_corrs.sort(key=lambda x: abs(x["change"]), reverse=True)
        
        return rolling_corrs
    
    def _detect_correlation_regime(
        self,
        corr_matrix: np.ndarray,
        returns_matrix: np.ndarray,
        symbols: list[str],
    ) -> dict[str, Any]:
        """Detect current correlation regime."""
        # Average off-diagonal correlation
        n = corr_matrix.shape[0]
        mask = ~np.eye(n, dtype=bool)
        avg_corr = np.mean(corr_matrix[mask])
        
        # Historical comparison (using rolling windows)
        window = 20
        if returns_matrix.shape[1] > window * 5:
            historical_corrs = []
            for t in range(window, returns_matrix.shape[1] - window, window):
                subset = returns_matrix[:, t-window:t]
                corr = np.corrcoef(subset)
                historical_corrs.append(np.mean(corr[mask]))
            
            percentile = (np.sum(np.array(historical_corrs) < avg_corr) / len(historical_corrs)) * 100
        else:
            percentile = 50
        
        # Determine regime
        if avg_corr > 0.7:
            regime = "high_correlation"
            description = "Assets moving together - systematic risk dominant"
        elif avg_corr > 0.4:
            regime = "moderate_correlation"
            description = "Normal correlation environment"
        elif avg_corr > 0.1:
            regime = "low_correlation"
            description = "Good diversification potential"
        else:
            regime = "decorrelated"
            description = "Assets largely independent - excellent for diversification"
        
        return {
            "regime": regime,
            "average_correlation": round(avg_corr, 3),
            "percentile_rank": round(percentile, 1),
            "description": description,
            "diversification_potential": "high" if avg_corr < 0.3 else "moderate" if avg_corr < 0.5 else "low",
        }
    
    def _analyze_pairs(
        self,
        returns_matrix: np.ndarray,
        symbols: list[str],
    ) -> list[dict]:
        """Analyze all pairs for trading opportunities."""
        pairs = []
        n = len(symbols)
        
        for i in range(n):
            for j in range(i + 1, n):
                returns1 = returns_matrix[i]
                returns2 = returns_matrix[j]
                
                # Correlation
                corr = np.corrcoef(returns1, returns2)[0, 1]
                
                # Only consider correlated pairs for pair trading
                if corr < 0.5:
                    continue
                
                # Simple spread analysis using cumulative returns
                cum_ret1 = np.cumsum(returns1)
                cum_ret2 = np.cumsum(returns2)
                
                # Estimate hedge ratio
                hedge_ratio = np.std(returns1) / np.std(returns2)
                spread = cum_ret1 - hedge_ratio * cum_ret2
                
                # Z-score
                spread_mean = np.mean(spread)
                spread_std = np.std(spread)
                z_score = (spread[-1] - spread_mean) / spread_std if spread_std > 0 else 0
                
                # Half-life
                half_life = self._calculate_half_life(spread)
                
                # Signal
                if abs(z_score) > self.Z_SCORE_ENTRY:
                    signal = "SHORT_SPREAD" if z_score > 0 else "LONG_SPREAD"
                else:
                    signal = None
                
                pairs.append({
                    "symbol1": symbols[i],
                    "symbol2": symbols[j],
                    "correlation": round(corr, 3),
                    "hedge_ratio": round(hedge_ratio, 4),
                    "z_score": round(z_score, 3),
                    "half_life": round(half_life, 1) if half_life else None,
                    "signal": signal,
                    "trade_quality": self._assess_pair_quality(corr, z_score, half_life),
                })
        
        # Sort by trade quality
        quality_order = {"excellent": 0, "good": 1, "moderate": 2, "poor": 3}
        pairs.sort(key=lambda x: (quality_order.get(x["trade_quality"], 4), -abs(x["z_score"])))
        
        return pairs
    
    def _cointegration_test(
        self,
        prices1: np.ndarray,
        prices2: np.ndarray,
    ) -> tuple[float, float, np.ndarray]:
        """
        Simplified Engle-Granger cointegration test.
        
        Returns p-value approximation, hedge ratio, and residuals.
        """
        # OLS regression: prices1 = beta * prices2 + residual
        log_p1 = np.log(prices1)
        log_p2 = np.log(prices2)
        
        # Simple OLS
        X = np.column_stack([np.ones(len(log_p2)), log_p2])
        coeffs = np.linalg.lstsq(X, log_p1, rcond=None)[0]
        hedge_ratio = coeffs[1]
        
        residuals = log_p1 - (coeffs[0] + hedge_ratio * log_p2)
        
        # ADF-like stationarity test (simplified)
        # Test if residuals are mean-reverting
        lag_residuals = residuals[:-1]
        diff_residuals = np.diff(residuals)
        
        # Regression: d(residual) = gamma * residual(-1) + error
        gamma = np.corrcoef(diff_residuals, lag_residuals)[0, 1] * np.std(diff_residuals) / np.std(lag_residuals)
        
        # Approximate p-value based on gamma
        # More negative gamma = more mean-reverting = lower p-value
        if gamma < -0.1:
            p_value = 0.01
        elif gamma < -0.05:
            p_value = 0.05
        elif gamma < 0:
            p_value = 0.10
        else:
            p_value = 0.50
        
        return p_value, hedge_ratio, residuals
    
    def _calculate_half_life(self, spread: np.ndarray) -> float | None:
        """Calculate half-life of mean reversion."""
        if len(spread) < 10:
            return None
        
        lag_spread = spread[:-1]
        diff_spread = np.diff(spread)
        
        # Regression coefficient
        if np.var(lag_spread) > 0:
            corr = np.corrcoef(diff_spread, lag_spread)[0, 1]
            beta = corr * np.std(diff_spread) / np.std(lag_spread)
            
            if beta < 0:
                half_life = -np.log(2) / beta
                return half_life if half_life > 0 and half_life < len(spread) else None
        
        return None
    
    def _calculate_beta(
        self, returns1: np.ndarray, returns2: np.ndarray
    ) -> float:
        """Calculate beta of returns1 to returns2."""
        covariance = np.cov(returns1, returns2)[0, 1]
        variance = np.var(returns2)
        return covariance / variance if variance > 0 else 1.0
    
    def _calculate_diversification_metrics(
        self,
        corr_matrix: np.ndarray,
        symbols: list[str],
    ) -> dict[str, Any]:
        """Calculate portfolio diversification metrics."""
        n = len(symbols)
        
        # Average pairwise correlation
        mask = ~np.eye(n, dtype=bool)
        avg_corr = np.mean(corr_matrix[mask])
        
        # Diversification ratio
        # DR = sum of individual volatilities / portfolio volatility
        # Simplified using correlation
        div_ratio = n / (1 + (n - 1) * avg_corr) if avg_corr < 1 else 1
        
        # Effective number of independent assets
        # Based on eigenvalue analysis
        eigenvalues = np.linalg.eigvalsh(corr_matrix)
        eigenvalues = np.maximum(eigenvalues, 0)  # Ensure non-negative
        total = np.sum(eigenvalues)
        if total > 0:
            eff_n = np.exp(-np.sum((eigenvalues / total) * np.log(eigenvalues / total + 1e-10)))
        else:
            eff_n = 1
        
        # Most correlated groups
        # Simple clustering based on correlation threshold
        groups = self._find_correlated_groups(corr_matrix, symbols, threshold=0.7)
        
        return {
            "average_correlation": round(avg_corr, 3),
            "diversification_ratio": round(div_ratio, 2),
            "effective_assets": round(eff_n, 1),
            "actual_assets": n,
            "correlation_clusters": groups,
            "diversification_grade": self._grade_diversification(avg_corr, eff_n, n),
        }
    
    def _find_correlated_groups(
        self,
        corr_matrix: np.ndarray,
        symbols: list[str],
        threshold: float = 0.7,
    ) -> list[list[str]]:
        """Find groups of highly correlated assets."""
        n = len(symbols)
        visited = set()
        groups = []
        
        for i in range(n):
            if i in visited:
                continue
            
            group = [symbols[i]]
            visited.add(i)
            
            for j in range(i + 1, n):
                if j not in visited and corr_matrix[i, j] > threshold:
                    group.append(symbols[j])
                    visited.add(j)
            
            if len(group) > 1:
                groups.append(group)
        
        return groups
    
    def _grade_diversification(
        self, avg_corr: float, eff_n: float, actual_n: int
    ) -> str:
        """Grade portfolio diversification."""
        ratio = eff_n / actual_n if actual_n > 0 else 0
        
        if avg_corr < 0.3 and ratio > 0.7:
            return "A"
        elif avg_corr < 0.4 and ratio > 0.5:
            return "B"
        elif avg_corr < 0.5 and ratio > 0.4:
            return "C"
        else:
            return "D"
    
    def _assess_pair_quality(
        self, correlation: float, z_score: float, half_life: float | None
    ) -> str:
        """Assess quality of a pair trading opportunity."""
        score = 0
        
        # High correlation is good for pair trading
        if correlation > 0.8:
            score += 2
        elif correlation > 0.6:
            score += 1
        
        # Extreme z-score is good
        if abs(z_score) > 2.5:
            score += 2
        elif abs(z_score) > 2:
            score += 1
        
        # Reasonable half-life
        if half_life:
            if 5 < half_life < 30:
                score += 2
            elif half_life < 60:
                score += 1
        
        if score >= 5:
            return "excellent"
        elif score >= 3:
            return "good"
        elif score >= 1:
            return "moderate"
        else:
            return "poor"
    
    def _categorize_beta(self, beta: float) -> str:
        """Categorize a stock based on its beta."""
        if beta > 1.5:
            return "high_beta_aggressive"
        elif beta > 1.2:
            return "high_beta"
        elif beta > 0.8:
            return "market_beta"
        elif beta > 0.5:
            return "low_beta"
        elif beta > 0:
            return "defensive"
        else:
            return "negative_beta_hedge"
