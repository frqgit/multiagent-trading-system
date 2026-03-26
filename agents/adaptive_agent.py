"""Adaptive Learning Agent — Machine learning-based strategy adaptation and regime detection.

Implements:
- Market regime classification (Hidden Markov Model concept)
- Feature importance analysis
- Strategy performance tracking
- Adaptive parameter tuning
- Ensemble signal generation
- Performance attribution
"""

from __future__ import annotations

import asyncio
import logging
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class StrategyPerformance:
    """Track strategy performance metrics."""
    strategy_name: str
    total_trades: int = 0
    winning_trades: int = 0
    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    recent_win_rate: float = 0.0
    regime_performance: dict = field(default_factory=dict)


@dataclass
class MarketRegime:
    """Current market regime classification."""
    regime: str  # trending_up, trending_down, ranging, volatile, calm
    confidence: float
    features: dict
    recommended_strategies: list[str]


class AdaptiveLearningAgent:
    """
    Machine learning-based adaptive strategy selection and parameter tuning.
    
    Capabilities:
    - Market regime detection using statistical features
    - Strategy performance tracking and ranking
    - Adaptive weight allocation across strategies
    - Feature importance for signal generation
    - Ensemble prediction combining multiple signals
    - Self-improving through performance feedback
    """

    name = "AdaptiveLearningAgent"
    
    # Strategy weights storage
    WEIGHTS_FILE = "strategy_weights.json"
    PERFORMANCE_FILE = "strategy_performance.json"
    
    # Regime definitions
    REGIMES = ["trending_up", "trending_down", "ranging", "volatile", "calm"]
    
    # Default strategy pool
    DEFAULT_STRATEGIES = [
        "ma_crossover",
        "rsi_mean_reversion",
        "momentum",
        "breakout",
        "macd",
        "bollinger",
    ]
    
    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # Load persisted weights and performance
        self.strategy_weights = self._load_weights()
        self.strategy_performance = self._load_performance()
    
    async def analyze(
        self,
        symbol: str,
        price_data: list[dict],
        available_signals: dict[str, dict] | None = None,
    ) -> dict[str, Any]:
        """
        Adaptive analysis combining regime detection and strategy selection.
        
        Args:
            symbol: Stock symbol
            price_data: OHLCV data
            available_signals: Pre-computed signals from other agents
            
        Returns:
            Adaptive analysis with regime, strategy recommendations, and ensemble signal
        """
        logger.info("[%s] Adaptive analysis for %s", self.name, symbol)
        
        if len(price_data) < 50:
            return {"error": "Insufficient data", "symbol": symbol}
        
        closes = np.array([d["close"] for d in price_data])
        highs = np.array([d["high"] for d in price_data])
        lows = np.array([d["low"] for d in price_data])
        volumes = np.array([d["volume"] for d in price_data])
        
        # Calculate features for regime detection
        features = self._calculate_features(closes, highs, lows, volumes)
        
        # Detect market regime
        regime = self._detect_regime(features)
        
        # Get strategy recommendations for current regime
        strategy_recs = self._recommend_strategies(regime, self.strategy_performance)
        
        # Calculate adaptive weights
        adaptive_weights = self._calculate_adaptive_weights(regime, self.strategy_performance)
        
        # Generate ensemble signal if signals provided
        ensemble = None
        if available_signals:
            ensemble = self._generate_ensemble_signal(available_signals, adaptive_weights)
        
        # Feature importance
        feature_importance = self._calculate_feature_importance(features, closes)
        
        # Regime history (simulated from recent data)
        regime_history = self._estimate_regime_history(closes, highs, lows, volumes)
        
        return {
            "symbol": symbol,
            "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "market_regime": {
                "current": regime.regime,
                "confidence": round(regime.confidence, 2),
                "description": self._regime_description(regime.regime),
                "recommended_strategies": regime.recommended_strategies[:5],
            },
            "features": features,
            "feature_importance": feature_importance,
            "strategy_recommendations": strategy_recs,
            "adaptive_weights": {k: round(v, 3) for k, v in adaptive_weights.items()},
            "ensemble_signal": ensemble,
            "regime_history": regime_history[-20:],  # Last 20 observations
            "adaptation_stats": {
                "total_tracked_trades": sum(
                    p.get("total_trades", 0) for p in self.strategy_performance.values()
                ),
                "best_performing_strategy": self._get_best_strategy(),
                "worst_performing_strategy": self._get_worst_strategy(),
            },
        }
    
    def update_performance(
        self,
        strategy_name: str,
        trade_result: dict,
        regime: str,
    ) -> None:
        """
        Update strategy performance based on trade result.
        
        Args:
            strategy_name: Name of the strategy
            trade_result: Dict with 'pnl', 'win' (bool), 'return_pct'
            regime: Market regime during the trade
        """
        if strategy_name not in self.strategy_performance:
            self.strategy_performance[strategy_name] = {
                "total_trades": 0,
                "winning_trades": 0,
                "total_return": 0.0,
                "returns": [],
                "regime_performance": {},
            }
        
        perf = self.strategy_performance[strategy_name]
        perf["total_trades"] += 1
        
        if trade_result.get("win", False):
            perf["winning_trades"] += 1
        
        perf["total_return"] += trade_result.get("return_pct", 0)
        perf["returns"].append(trade_result.get("return_pct", 0))
        
        # Track regime-specific performance
        if regime not in perf["regime_performance"]:
            perf["regime_performance"][regime] = {
                "trades": 0,
                "wins": 0,
                "total_return": 0.0,
            }
        
        regime_perf = perf["regime_performance"][regime]
        regime_perf["trades"] += 1
        if trade_result.get("win", False):
            regime_perf["wins"] += 1
        regime_perf["total_return"] += trade_result.get("return_pct", 0)
        
        # Save updated performance
        self._save_performance()
        
        # Update weights based on new performance
        self._update_weights_from_performance()
    
    def _calculate_features(
        self,
        closes: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        volumes: np.ndarray,
    ) -> dict[str, float]:
        """Calculate statistical features for regime detection."""
        returns = np.diff(np.log(closes))
        
        # Trend features
        ma20 = np.mean(closes[-20:])
        ma50 = np.mean(closes[-50:]) if len(closes) >= 50 else ma20
        
        price_vs_ma20 = (closes[-1] - ma20) / ma20
        price_vs_ma50 = (closes[-1] - ma50) / ma50
        ma_spread = (ma20 - ma50) / ma50 if ma50 != 0 else 0
        
        # Momentum features
        momentum_5d = (closes[-1] - closes[-5]) / closes[-5] if closes[-5] != 0 else 0
        momentum_20d = (closes[-1] - closes[-20]) / closes[-20] if closes[-20] != 0 else 0
        
        # Volatility features
        volatility_10d = np.std(returns[-10:]) * np.sqrt(252) if len(returns) >= 10 else 0
        volatility_20d = np.std(returns[-20:]) * np.sqrt(252) if len(returns) >= 20 else 0
        vol_ratio = volatility_10d / volatility_20d if volatility_20d > 0 else 1
        
        # Range features
        atr_10 = np.mean(highs[-10:] - lows[-10:])
        atr_ratio = atr_10 / closes[-1] if closes[-1] != 0 else 0
        
        # Volume features
        vol_ratio_20d = volumes[-1] / np.mean(volumes[-20:]) if np.mean(volumes[-20:]) > 0 else 1
        vol_trend = np.mean(volumes[-5:]) / np.mean(volumes[-20:]) if np.mean(volumes[-20:]) > 0 else 1
        
        # Autocorrelation (mean reversion indicator)
        if len(returns) >= 20:
            autocorr = np.corrcoef(returns[:-1][-20:], returns[1:][-20:])[0, 1]
        else:
            autocorr = 0
        
        # RSI-like features
        gains = returns[returns > 0]
        losses = -returns[returns < 0]
        avg_gain = np.mean(gains[-14:]) if len(gains) >= 14 else np.mean(gains) if len(gains) > 0 else 0
        avg_loss = np.mean(losses[-14:]) if len(losses) >= 14 else np.mean(losses) if len(losses) > 0 else 1e-10
        rsi = 100 - (100 / (1 + avg_gain / avg_loss)) if avg_loss > 0 else 50
        
        # Trend strength (ADX-like)
        up_moves = np.maximum(np.diff(highs[-15:]), 0)
        down_moves = np.maximum(-np.diff(lows[-15:]), 0)
        trend_strength = np.abs(np.sum(up_moves) - np.sum(down_moves)) / (np.sum(up_moves) + np.sum(down_moves) + 1e-10)
        
        return {
            "price_vs_ma20": round(price_vs_ma20, 4),
            "price_vs_ma50": round(price_vs_ma50, 4),
            "ma_spread": round(ma_spread, 4),
            "momentum_5d": round(momentum_5d, 4),
            "momentum_20d": round(momentum_20d, 4),
            "volatility_10d": round(volatility_10d, 4),
            "volatility_20d": round(volatility_20d, 4),
            "vol_expansion": round(vol_ratio, 4),
            "atr_ratio": round(atr_ratio, 4),
            "volume_ratio": round(vol_ratio_20d, 4),
            "volume_trend": round(vol_trend, 4),
            "autocorrelation": round(autocorr, 4) if not np.isnan(autocorr) else 0,
            "rsi": round(rsi, 2),
            "trend_strength": round(trend_strength, 4),
        }
    
    def _detect_regime(self, features: dict[str, float]) -> MarketRegime:
        """Detect market regime based on features."""
        # Rule-based regime detection (could be replaced with ML model)
        
        price_vs_ma = features["price_vs_ma20"]
        momentum = features["momentum_20d"]
        volatility = features["volatility_10d"]
        vol_expansion = features["vol_expansion"]
        trend_strength = features["trend_strength"]
        autocorr = features["autocorrelation"]
        
        # Scoring for each regime
        scores = {}
        
        # Trending up
        scores["trending_up"] = (
            max(0, price_vs_ma * 10) +
            max(0, momentum * 10) +
            trend_strength * 5 +
            max(0, -autocorr * 3)  # Low autocorr = trending
        )
        
        # Trending down
        scores["trending_down"] = (
            max(0, -price_vs_ma * 10) +
            max(0, -momentum * 10) +
            trend_strength * 5 +
            max(0, -autocorr * 3)
        )
        
        # Ranging (mean reversion)
        scores["ranging"] = (
            (1 - trend_strength) * 8 +
            max(0, autocorr * 5) +  # High autocorr = mean reverting
            (1 if abs(price_vs_ma) < 0.02 else 0) * 5
        )
        
        # Volatile
        scores["volatile"] = (
            volatility * 20 +
            vol_expansion * 10 +
            features["atr_ratio"] * 100
        )
        
        # Calm
        scores["calm"] = (
            (1 - min(volatility, 1)) * 10 +
            (1 if volatility < 0.15 else 0) * 10 +
            (1 if features["atr_ratio"] < 0.02 else 0) * 5
        )
        
        # Normalize scores
        total = sum(scores.values())
        if total > 0:
            scores = {k: v / total for k, v in scores.items()}
        
        # Select regime with highest score
        regime = max(scores, key=scores.get)
        confidence = scores[regime]
        
        # Get recommended strategies for this regime
        recommendations = self._strategies_for_regime(regime)
        
        return MarketRegime(
            regime=regime,
            confidence=confidence,
            features=features,
            recommended_strategies=recommendations,
        )
    
    def _strategies_for_regime(self, regime: str) -> list[str]:
        """Get recommended strategies for a regime."""
        recommendations = {
            "trending_up": ["momentum", "breakout", "ma_crossover"],
            "trending_down": ["momentum", "breakout", "ma_crossover"],
            "ranging": ["rsi_mean_reversion", "bollinger", "macd"],
            "volatile": ["bollinger", "rsi_mean_reversion"],
            "calm": ["breakout", "ma_crossover"],
        }
        return recommendations.get(regime, self.DEFAULT_STRATEGIES)
    
    def _regime_description(self, regime: str) -> str:
        """Get human-readable regime description."""
        descriptions = {
            "trending_up": "Strong uptrend with momentum - favor trend-following strategies",
            "trending_down": "Strong downtrend - favor trend-following short strategies",
            "ranging": "Sideways market - favor mean reversion strategies",
            "volatile": "High volatility environment - reduce position sizes, use wider stops",
            "calm": "Low volatility - potential for breakout, use tighter stops",
        }
        return descriptions.get(regime, "Unknown regime")
    
    def _recommend_strategies(
        self,
        regime: MarketRegime,
        performance_history: dict,
    ) -> list[dict]:
        """Recommend strategies based on regime and performance."""
        recommendations = []
        
        for strategy in regime.recommended_strategies:
            perf = performance_history.get(strategy, {})
            regime_perf = perf.get("regime_performance", {}).get(regime.regime, {})
            
            total_trades = perf.get("total_trades", 0)
            wins = perf.get("winning_trades", 0)
            win_rate = wins / total_trades if total_trades > 0 else 0.5
            
            # Regime-specific stats
            regime_trades = regime_perf.get("trades", 0)
            regime_wins = regime_perf.get("wins", 0)
            regime_win_rate = regime_wins / regime_trades if regime_trades > 0 else 0.5
            
            recommendations.append({
                "strategy": strategy,
                "overall_win_rate": round(win_rate, 3),
                "regime_win_rate": round(regime_win_rate, 3),
                "total_trades": total_trades,
                "regime_trades": regime_trades,
                "confidence": round(regime.confidence * regime_win_rate, 3),
            })
        
        # Sort by confidence
        recommendations.sort(key=lambda x: x["confidence"], reverse=True)
        
        return recommendations
    
    def _calculate_adaptive_weights(
        self,
        regime: MarketRegime,
        performance_history: dict,
    ) -> dict[str, float]:
        """Calculate adaptive weights for each strategy."""
        weights = {}
        
        for strategy in self.DEFAULT_STRATEGIES:
            base_weight = 1.0 / len(self.DEFAULT_STRATEGIES)
            
            # Adjust based on regime appropriateness
            if strategy in regime.recommended_strategies:
                regime_factor = 1.5
            else:
                regime_factor = 0.5
            
            # Adjust based on performance
            perf = performance_history.get(strategy, {})
            total_trades = perf.get("total_trades", 0)
            
            if total_trades > 10:
                win_rate = perf.get("winning_trades", 0) / total_trades
                perf_factor = 0.5 + win_rate  # 0.5 to 1.5
            else:
                perf_factor = 1.0  # Neutral if not enough trades
            
            # Regime-specific performance adjustment
            regime_perf = perf.get("regime_performance", {}).get(regime.regime, {})
            regime_trades = regime_perf.get("trades", 0)
            
            if regime_trades > 5:
                regime_win_rate = regime_perf.get("wins", 0) / regime_trades
                regime_factor *= (0.5 + regime_win_rate)
            
            weights[strategy] = base_weight * regime_factor * perf_factor
        
        # Normalize weights
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}
        
        return weights
    
    def _generate_ensemble_signal(
        self,
        signals: dict[str, dict],
        weights: dict[str, float],
    ) -> dict[str, Any]:
        """Generate ensemble signal from multiple strategy signals."""
        # Convert signals to numeric scores
        signal_values = {
            "STRONG_BUY": 2,
            "BUY": 1,
            "WEAK_BUY": 0.5,
            "HOLD": 0,
            "WEAK_SELL": -0.5,
            "SELL": -1,
            "STRONG_SELL": -2,
        }
        
        weighted_score = 0
        total_weight = 0
        signal_breakdown = []
        
        for strategy, signal in signals.items():
            if strategy not in weights:
                continue
            
            signal_type = signal.get("signal", "HOLD")
            score = signal_values.get(signal_type, 0)
            weight = weights.get(strategy, 0)
            
            weighted_score += score * weight
            total_weight += weight
            
            signal_breakdown.append({
                "strategy": strategy,
                "signal": signal_type,
                "weight": round(weight, 3),
                "contribution": round(score * weight, 3),
            })
        
        # Final score
        if total_weight > 0:
            final_score = weighted_score / total_weight
        else:
            final_score = 0
        
        # Convert to signal
        if final_score > 1.5:
            ensemble_signal = "STRONG_BUY"
            confidence = 0.9
        elif final_score > 0.75:
            ensemble_signal = "BUY"
            confidence = 0.7
        elif final_score > 0.25:
            ensemble_signal = "WEAK_BUY"
            confidence = 0.5
        elif final_score < -1.5:
            ensemble_signal = "STRONG_SELL"
            confidence = 0.9
        elif final_score < -0.75:
            ensemble_signal = "SELL"
            confidence = 0.7
        elif final_score < -0.25:
            ensemble_signal = "WEAK_SELL"
            confidence = 0.5
        else:
            ensemble_signal = "HOLD"
            confidence = 0.4
        
        return {
            "signal": ensemble_signal,
            "score": round(final_score, 3),
            "confidence": round(confidence, 2),
            "breakdown": sorted(signal_breakdown, key=lambda x: abs(x["contribution"]), reverse=True),
            "agreement": self._calculate_signal_agreement(signals),
        }
    
    def _calculate_signal_agreement(self, signals: dict[str, dict]) -> float:
        """Calculate agreement level among signals."""
        buy_count = 0
        sell_count = 0
        hold_count = 0
        
        for signal in signals.values():
            sig = signal.get("signal", "HOLD")
            if "BUY" in sig:
                buy_count += 1
            elif "SELL" in sig:
                sell_count += 1
            else:
                hold_count += 1
        
        total = buy_count + sell_count + hold_count
        if total == 0:
            return 0.5
        
        # Max proportion
        max_prop = max(buy_count, sell_count, hold_count) / total
        
        return round(max_prop, 2)
    
    def _calculate_feature_importance(
        self,
        features: dict[str, float],
        closes: np.ndarray,
    ) -> dict[str, float]:
        """Estimate feature importance for prediction."""
        returns = np.diff(np.log(closes))
        forward_return = returns[-1] if len(returns) > 0 else 0
        
        # Simple correlation-based importance
        importance = {}
        
        # Features that might correlate with next-day return
        importance["momentum_5d"] = abs(np.corrcoef([features["momentum_5d"]], [forward_return])[0, 1]) if forward_return != 0 else 0.1
        importance["price_vs_ma20"] = 0.15  # Generally important
        importance["volatility_10d"] = 0.12
        importance["rsi"] = 0.10
        importance["trend_strength"] = 0.13
        importance["volume_ratio"] = 0.08
        
        # Normalize
        total = sum(importance.values())
        if total > 0:
            importance = {k: round(v / total, 3) for k, v in importance.items()}
        
        return importance
    
    def _estimate_regime_history(
        self,
        closes: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        volumes: np.ndarray,
        window: int = 20,
    ) -> list[dict]:
        """Estimate historical regimes."""
        history = []
        
        for i in range(window * 2, len(closes)):
            subset_close = closes[i-window*2:i]
            subset_high = highs[i-window*2:i]
            subset_low = lows[i-window*2:i]
            subset_vol = volumes[i-window*2:i]
            
            features = self._calculate_features(subset_close, subset_high, subset_low, subset_vol)
            regime = self._detect_regime(features)
            
            history.append({
                "index": i,
                "regime": regime.regime,
                "confidence": round(regime.confidence, 2),
            })
        
        return history
    
    def _get_best_strategy(self) -> str | None:
        """Get the best performing strategy."""
        best = None
        best_score = -float('inf')
        
        for strategy, perf in self.strategy_performance.items():
            trades = perf.get("total_trades", 0)
            if trades < 5:
                continue
            
            win_rate = perf.get("winning_trades", 0) / trades
            total_return = perf.get("total_return", 0)
            
            score = win_rate * 0.5 + total_return * 0.001
            
            if score > best_score:
                best_score = score
                best = strategy
        
        return best
    
    def _get_worst_strategy(self) -> str | None:
        """Get the worst performing strategy."""
        worst = None
        worst_score = float('inf')
        
        for strategy, perf in self.strategy_performance.items():
            trades = perf.get("total_trades", 0)
            if trades < 5:
                continue
            
            win_rate = perf.get("winning_trades", 0) / trades
            total_return = perf.get("total_return", 0)
            
            score = win_rate * 0.5 + total_return * 0.001
            
            if score < worst_score:
                worst_score = score
                worst = strategy
        
        return worst
    
    def _update_weights_from_performance(self) -> None:
        """Update strategy weights based on performance."""
        new_weights = {}
        
        for strategy in self.DEFAULT_STRATEGIES:
            perf = self.strategy_performance.get(strategy, {})
            trades = perf.get("total_trades", 0)
            
            if trades > 10:
                win_rate = perf.get("winning_trades", 0) / trades
                returns = perf.get("returns", [])
                sharpe = self._calculate_sharpe(returns) if returns else 0
                
                # Weight based on win rate and sharpe
                weight = (win_rate + 0.5) * (1 + sharpe * 0.1)
            else:
                weight = 1.0  # Default weight
            
            new_weights[strategy] = weight
        
        # Normalize
        total = sum(new_weights.values())
        if total > 0:
            self.strategy_weights = {k: v / total for k, v in new_weights.items()}
        
        self._save_weights()
    
    def _calculate_sharpe(self, returns: list[float]) -> float:
        """Calculate Sharpe ratio from returns."""
        if len(returns) < 2:
            return 0
        
        avg_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0
        
        # Annualized
        return (avg_return / std_return) * np.sqrt(252)
    
    def _load_weights(self) -> dict[str, float]:
        """Load strategy weights from file."""
        weights_path = self.data_dir / self.WEIGHTS_FILE
        
        if weights_path.exists():
            try:
                with open(weights_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("[%s] Failed to load weights: %s", self.name, e)
        
        # Default equal weights
        return {s: 1.0 / len(self.DEFAULT_STRATEGIES) for s in self.DEFAULT_STRATEGIES}
    
    def _save_weights(self) -> None:
        """Save strategy weights to file."""
        weights_path = self.data_dir / self.WEIGHTS_FILE
        
        try:
            with open(weights_path, "w") as f:
                json.dump(self.strategy_weights, f, indent=2)
        except Exception as e:
            logger.warning("[%s] Failed to save weights: %s", self.name, e)
    
    def _load_performance(self) -> dict[str, dict]:
        """Load strategy performance from file."""
        perf_path = self.data_dir / self.PERFORMANCE_FILE
        
        if perf_path.exists():
            try:
                with open(perf_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("[%s] Failed to load performance: %s", self.name, e)
        
        return {}
    
    def _save_performance(self) -> None:
        """Save strategy performance to file."""
        perf_path = self.data_dir / self.PERFORMANCE_FILE
        
        try:
            with open(perf_path, "w") as f:
                json.dump(self.strategy_performance, f, indent=2)
        except Exception as e:
            logger.warning("[%s] Failed to save performance: %s", self.name, e)
