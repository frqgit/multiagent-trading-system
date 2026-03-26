"""Portfolio Optimization Agent — Modern Portfolio Theory, position sizing, and portfolio balancing.

Implements:
- Mean-Variance Optimization (Markowitz)
- Black-Litterman model integration
- Kelly Criterion position sizing
- Risk Parity allocation
- Sharpe Ratio optimization
- Portfolio correlation analysis
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.optimize import minimize

from tools.stock_api import fetch_stock_data

logger = logging.getLogger(__name__)


@dataclass
class PortfolioMetrics:
    """Portfolio risk/return metrics."""
    expected_return: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    var_95: float  # Value at Risk 95%
    cvar_95: float  # Conditional VaR 95%
    beta: float
    alpha: float


@dataclass 
class OptimizedPortfolio:
    """Result of portfolio optimization."""
    weights: dict[str, float]
    metrics: PortfolioMetrics
    efficient_frontier: list[dict]
    rebalance_trades: list[dict]
    risk_contributions: dict[str, float]


class PortfolioOptimizationAgent:
    """
    Optimizes portfolio allocation using Modern Portfolio Theory and advanced techniques.
    
    Capabilities:
    - Mean-Variance Optimization (Markowitz efficient frontier)
    - Maximum Sharpe Ratio portfolio
    - Minimum Variance portfolio
    - Risk Parity allocation
    - Kelly Criterion position sizing
    - Black-Litterman with analyst views
    """

    name = "PortfolioOptimizationAgent"
    
    # Risk-free rate assumption (annualized)
    RISK_FREE_RATE = 0.05  # 5%
    
    # Optimization constraints
    MAX_POSITION_SIZE = 0.30  # 30% max per asset
    MIN_POSITION_SIZE = 0.02  # 2% min per asset
    
    async def analyze(
        self,
        symbols: list[str],
        current_weights: dict[str, float] | None = None,
        target_risk: float | None = None,
        optimization_goal: str = "max_sharpe",
        analyst_views: dict[str, float] | None = None,
        lookback_days: int = 252,
    ) -> dict[str, Any]:
        """
        Analyze and optimize a portfolio.
        
        Args:
            symbols: List of stock symbols
            current_weights: Current portfolio weights (optional)
            target_risk: Target portfolio volatility (optional)
            optimization_goal: 'max_sharpe', 'min_variance', 'risk_parity', 'target_return'
            analyst_views: Expected returns from analyst estimates (for Black-Litterman)
            lookback_days: Historical data lookback period
            
        Returns:
            Optimized portfolio weights and metrics
        """
        logger.info("[%s] Optimizing portfolio for %s symbols", self.name, len(symbols))
        
        if len(symbols) < 2:
            return {"error": "Portfolio optimization requires at least 2 symbols", "symbols": symbols}
        
        # Fetch historical data for all symbols
        try:
            price_data = await self._fetch_price_histories(symbols, lookback_days)
        except Exception as e:
            logger.error("[%s] Failed to fetch price data: %s", self.name, e)
            return {"error": f"Failed to fetch price data: {e}", "symbols": symbols}
        
        if len(price_data) < 2:
            return {"error": "Insufficient data for optimization", "symbols": symbols}
        
        # Calculate returns and covariance matrix
        returns_matrix, valid_symbols = self._calculate_returns(price_data)
        if returns_matrix is None or len(valid_symbols) < 2:
            return {"error": "Insufficient return data for optimization", "symbols": symbols}
        
        mean_returns = np.mean(returns_matrix, axis=0) * 252  # Annualized
        cov_matrix = np.cov(returns_matrix.T) * 252  # Annualized
        
        # Apply Black-Litterman if analyst views provided
        if analyst_views:
            mean_returns = self._black_litterman_adjust(
                mean_returns, cov_matrix, valid_symbols, analyst_views
            )
        
        # Run optimization based on goal
        if optimization_goal == "max_sharpe":
            weights = self._optimize_sharpe(mean_returns, cov_matrix)
        elif optimization_goal == "min_variance":
            weights = self._optimize_min_variance(cov_matrix)
        elif optimization_goal == "risk_parity":
            weights = self._optimize_risk_parity(cov_matrix)
        elif optimization_goal == "target_risk" and target_risk:
            weights = self._optimize_target_risk(mean_returns, cov_matrix, target_risk)
        else:
            weights = self._optimize_sharpe(mean_returns, cov_matrix)
        
        # Calculate portfolio metrics
        metrics = self._calculate_portfolio_metrics(
            weights, mean_returns, cov_matrix, returns_matrix
        )
        
        # Calculate efficient frontier points
        efficient_frontier = self._calculate_efficient_frontier(mean_returns, cov_matrix)
        
        # Calculate risk contributions
        risk_contributions = self._calculate_risk_contributions(weights, cov_matrix, valid_symbols)
        
        # Calculate rebalance trades if current weights provided
        rebalance_trades = []
        if current_weights:
            rebalance_trades = self._calculate_rebalance_trades(
                current_weights, dict(zip(valid_symbols, weights)), valid_symbols
            )
        
        # Kelly Criterion position sizing
        kelly_fractions = self._kelly_criterion(mean_returns, cov_matrix, valid_symbols)
        
        # Correlation matrix
        correlation_matrix = np.corrcoef(returns_matrix.T)
        correlations = {}
        for i, s1 in enumerate(valid_symbols):
            for j, s2 in enumerate(valid_symbols):
                if i < j:
                    correlations[f"{s1}-{s2}"] = round(correlation_matrix[i, j], 3)
        
        return {
            "symbols": valid_symbols,
            "optimization_goal": optimization_goal,
            "optimal_weights": {s: round(w, 4) for s, w in zip(valid_symbols, weights)},
            "portfolio_metrics": {
                "expected_return": round(metrics.expected_return * 100, 2),
                "volatility": round(metrics.volatility * 100, 2),
                "sharpe_ratio": round(metrics.sharpe_ratio, 3),
                "sortino_ratio": round(metrics.sortino_ratio, 3),
                "max_drawdown": round(metrics.max_drawdown * 100, 2),
                "var_95": round(metrics.var_95 * 100, 2),
                "cvar_95": round(metrics.cvar_95 * 100, 2),
            },
            "kelly_fractions": kelly_fractions,
            "risk_contributions": risk_contributions,
            "correlations": correlations,
            "efficient_frontier": efficient_frontier[:10],  # Top 10 points
            "rebalance_trades": rebalance_trades,
            "diversification_score": self._diversification_score(weights, correlation_matrix),
            "concentration_risk": self._concentration_risk(weights),
        }
    
    async def _fetch_price_histories(
        self, symbols: list[str], lookback_days: int
    ) -> dict[str, list[float]]:
        """Fetch historical price data for all symbols."""
        async def fetch_one(symbol: str) -> tuple[str, list[float]]:
            try:
                data = await asyncio.to_thread(fetch_stock_data, symbol)
                prices = [p["close"] for p in data.price_history_30d]
                return (symbol, prices)
            except Exception as e:
                logger.warning("[%s] Failed to fetch %s: %s", self.name, symbol, e)
                return (symbol, [])
        
        results = await asyncio.gather(*[fetch_one(s) for s in symbols])
        return {sym: prices for sym, prices in results if prices}
    
    def _calculate_returns(
        self, price_data: dict[str, list[float]]
    ) -> tuple[np.ndarray | None, list[str]]:
        """Calculate daily returns matrix."""
        # Find minimum length across all series
        min_len = min(len(p) for p in price_data.values())
        if min_len < 20:
            return None, []
        
        valid_symbols = list(price_data.keys())
        returns_list = []
        
        for symbol in valid_symbols:
            prices = np.array(price_data[symbol][-min_len:])
            returns = np.diff(prices) / prices[:-1]
            returns_list.append(returns)
        
        return np.array(returns_list).T, valid_symbols
    
    def _optimize_sharpe(self, mean_returns: np.ndarray, cov_matrix: np.ndarray) -> np.ndarray:
        """Find the maximum Sharpe ratio portfolio."""
        n = len(mean_returns)
        
        def neg_sharpe(weights):
            port_return = np.dot(weights, mean_returns)
            port_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            return -(port_return - self.RISK_FREE_RATE) / port_vol
        
        constraints = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1},  # Weights sum to 1
        ]
        bounds = [(self.MIN_POSITION_SIZE, self.MAX_POSITION_SIZE) for _ in range(n)]
        
        result = minimize(
            neg_sharpe,
            np.ones(n) / n,  # Equal weight initial
            method="SLSQP",
            bounds=bounds,
            constraints=constraints
        )
        
        return result.x if result.success else np.ones(n) / n
    
    def _optimize_min_variance(self, cov_matrix: np.ndarray) -> np.ndarray:
        """Find the minimum variance portfolio."""
        n = cov_matrix.shape[0]
        
        def portfolio_variance(weights):
            return np.dot(weights.T, np.dot(cov_matrix, weights))
        
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
        bounds = [(self.MIN_POSITION_SIZE, self.MAX_POSITION_SIZE) for _ in range(n)]
        
        result = minimize(
            portfolio_variance,
            np.ones(n) / n,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints
        )
        
        return result.x if result.success else np.ones(n) / n
    
    def _optimize_risk_parity(self, cov_matrix: np.ndarray) -> np.ndarray:
        """Find the risk parity portfolio (equal risk contribution)."""
        n = cov_matrix.shape[0]
        target_risk = 1.0 / n
        
        def risk_parity_objective(weights):
            port_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            marginal_contrib = np.dot(cov_matrix, weights)
            risk_contrib = weights * marginal_contrib / port_vol
            return np.sum((risk_contrib - target_risk) ** 2)
        
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
        bounds = [(0.01, 0.50) for _ in range(n)]
        
        result = minimize(
            risk_parity_objective,
            np.ones(n) / n,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints
        )
        
        return result.x if result.success else np.ones(n) / n
    
    def _optimize_target_risk(
        self, mean_returns: np.ndarray, cov_matrix: np.ndarray, target_vol: float
    ) -> np.ndarray:
        """Find portfolio maximizing return for a target volatility."""
        n = len(mean_returns)
        
        def neg_return(weights):
            return -np.dot(weights, mean_returns)
        
        def vol_constraint(weights):
            return target_vol - np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        
        constraints = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1},
            {"type": "ineq", "fun": vol_constraint},
        ]
        bounds = [(self.MIN_POSITION_SIZE, self.MAX_POSITION_SIZE) for _ in range(n)]
        
        result = minimize(
            neg_return,
            np.ones(n) / n,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints
        )
        
        return result.x if result.success else np.ones(n) / n
    
    def _black_litterman_adjust(
        self,
        market_returns: np.ndarray,
        cov_matrix: np.ndarray,
        symbols: list[str],
        analyst_views: dict[str, float],
    ) -> np.ndarray:
        """Apply Black-Litterman model to incorporate analyst views."""
        tau = 0.05  # Confidence in market equilibrium
        
        # Build P matrix (view matrix) and Q vector (expected returns)
        views = [(symbols.index(s), r) for s, r in analyst_views.items() if s in symbols]
        if not views:
            return market_returns
        
        n_views = len(views)
        n_assets = len(symbols)
        
        P = np.zeros((n_views, n_assets))
        Q = np.zeros(n_views)
        
        for i, (asset_idx, expected_return) in enumerate(views):
            P[i, asset_idx] = 1
            Q[i] = expected_return
        
        # Omega: uncertainty in views (diagonal)
        omega = np.diag([tau * cov_matrix[v[0], v[0]] for v in views])
        
        # Black-Litterman formula
        M1 = np.linalg.inv(tau * cov_matrix)
        M2 = P.T @ np.linalg.inv(omega) @ P
        
        posterior_mean = np.linalg.inv(M1 + M2) @ (
            M1 @ market_returns + P.T @ np.linalg.inv(omega) @ Q
        )
        
        return posterior_mean
    
    def _calculate_portfolio_metrics(
        self,
        weights: np.ndarray,
        mean_returns: np.ndarray,
        cov_matrix: np.ndarray,
        returns_matrix: np.ndarray,
    ) -> PortfolioMetrics:
        """Calculate comprehensive portfolio metrics."""
        # Expected return and volatility
        expected_return = np.dot(weights, mean_returns)
        volatility = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        
        # Sharpe ratio
        sharpe = (expected_return - self.RISK_FREE_RATE) / volatility if volatility > 0 else 0
        
        # Portfolio daily returns
        portfolio_returns = np.dot(returns_matrix, weights)
        
        # Sortino ratio (downside deviation)
        negative_returns = portfolio_returns[portfolio_returns < 0]
        downside_std = np.std(negative_returns) * np.sqrt(252) if len(negative_returns) > 0 else volatility
        sortino = (expected_return - self.RISK_FREE_RATE) / downside_std if downside_std > 0 else 0
        
        # Maximum drawdown
        cumulative = np.cumprod(1 + portfolio_returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative - running_max) / running_max
        max_drawdown = np.min(drawdowns)
        
        # Value at Risk (95%)
        var_95 = np.percentile(portfolio_returns, 5) * np.sqrt(252)
        
        # Conditional VaR (Expected Shortfall)
        cvar_95 = np.mean(portfolio_returns[portfolio_returns <= np.percentile(portfolio_returns, 5)]) * np.sqrt(252)
        
        return PortfolioMetrics(
            expected_return=expected_return,
            volatility=volatility,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_drawdown,
            var_95=var_95,
            cvar_95=cvar_95,
            beta=1.0,  # Would need market returns to calculate
            alpha=expected_return - self.RISK_FREE_RATE,  # Simplified
        )
    
    def _calculate_efficient_frontier(
        self, mean_returns: np.ndarray, cov_matrix: np.ndarray, n_points: int = 20
    ) -> list[dict]:
        """Calculate efficient frontier points."""
        min_ret = np.min(mean_returns)
        max_ret = np.max(mean_returns)
        target_returns = np.linspace(min_ret, max_ret, n_points)
        
        frontier = []
        n = len(mean_returns)
        
        for target in target_returns:
            def portfolio_vol(weights):
                return np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            
            constraints = [
                {"type": "eq", "fun": lambda w: np.sum(w) - 1},
                {"type": "eq", "fun": lambda w, t=target: np.dot(w, mean_returns) - t},
            ]
            bounds = [(0, 1) for _ in range(n)]
            
            result = minimize(
                portfolio_vol,
                np.ones(n) / n,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints
            )
            
            if result.success:
                vol = result.fun
                frontier.append({
                    "return": round(target * 100, 2),
                    "volatility": round(vol * 100, 2),
                    "sharpe": round((target - self.RISK_FREE_RATE) / vol, 3) if vol > 0 else 0,
                })
        
        return frontier
    
    def _calculate_risk_contributions(
        self, weights: np.ndarray, cov_matrix: np.ndarray, symbols: list[str]
    ) -> dict[str, float]:
        """Calculate marginal risk contribution of each asset."""
        port_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        marginal = np.dot(cov_matrix, weights)
        risk_contrib = (weights * marginal) / port_vol
        total = np.sum(risk_contrib)
        
        return {s: round(rc / total * 100, 2) for s, rc in zip(symbols, risk_contrib)}
    
    def _calculate_rebalance_trades(
        self,
        current: dict[str, float],
        target: dict[str, float],
        symbols: list[str],
    ) -> list[dict]:
        """Calculate trades needed to rebalance portfolio."""
        trades = []
        for sym in symbols:
            curr = current.get(sym, 0)
            tgt = target.get(sym, 0)
            diff = tgt - curr
            
            if abs(diff) > 0.01:  # Only if > 1% difference
                trades.append({
                    "symbol": sym,
                    "action": "BUY" if diff > 0 else "SELL",
                    "weight_change": round(diff * 100, 2),
                    "from_weight": round(curr * 100, 2),
                    "to_weight": round(tgt * 100, 2),
                })
        
        return sorted(trades, key=lambda x: abs(x["weight_change"]), reverse=True)
    
    def _kelly_criterion(
        self,
        mean_returns: np.ndarray,
        cov_matrix: np.ndarray,
        symbols: list[str],
    ) -> dict[str, float]:
        """Calculate Kelly Criterion optimal fraction for each asset."""
        kelly = {}
        for i, sym in enumerate(symbols):
            # Simplified Kelly: (mean - risk_free) / variance
            var = cov_matrix[i, i]
            if var > 0:
                f = (mean_returns[i] - self.RISK_FREE_RATE) / var
                # Full Kelly is aggressive; use half-Kelly for safety
                kelly[sym] = round(max(0, min(f * 0.5, 0.5)) * 100, 2)
            else:
                kelly[sym] = 0
        return kelly
    
    def _diversification_score(
        self, weights: np.ndarray, correlation_matrix: np.ndarray
    ) -> float:
        """Calculate diversification score (0-100)."""
        # Higher score = better diversified
        weighted_avg_corr = 0
        total_weight = 0
        
        n = len(weights)
        for i in range(n):
            for j in range(i + 1, n):
                weight = weights[i] * weights[j]
                weighted_avg_corr += weight * abs(correlation_matrix[i, j])
                total_weight += weight
        
        if total_weight > 0:
            avg_corr = weighted_avg_corr / total_weight
            return round((1 - avg_corr) * 100, 1)
        return 100.0
    
    def _concentration_risk(self, weights: np.ndarray) -> dict[str, Any]:
        """Calculate portfolio concentration metrics."""
        # Herfindahl-Hirschman Index (HHI)
        hhi = np.sum(weights ** 2)
        
        # Effective number of assets
        eff_n = 1.0 / hhi if hhi > 0 else len(weights)
        
        # Top holdings
        sorted_weights = np.sort(weights)[::-1]
        top_3 = np.sum(sorted_weights[:3]) if len(sorted_weights) >= 3 else np.sum(sorted_weights)
        
        return {
            "hhi": round(hhi * 10000, 0),  # Scale to 0-10000
            "effective_assets": round(eff_n, 1),
            "top_3_concentration": round(top_3 * 100, 1),
            "risk_level": "high" if hhi > 0.25 else "medium" if hhi > 0.15 else "low",
        }
