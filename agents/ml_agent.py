"""ML Prediction Agent — LightGBM-based stock signal prediction.

Uses technical indicators as features to predict short-term price direction.
Supports training on historical data and generating BUY/SELL/HOLD signals
with confidence scores.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# LightGBM is optional
_lgb = None
_lgb_available = False


def _ensure_lgb():
    global _lgb, _lgb_available
    if _lgb is not None:
        return _lgb_available
    try:
        import lightgbm as lgb
        _lgb = lgb
        _lgb_available = True
    except ImportError:
        _lgb_available = False
    return _lgb_available


class MLPredictionAgent:
    """Uses LightGBM to generate BUY/SELL/HOLD signals from technical features."""

    name = "MLPredictionAgent"

    def __init__(self):
        self._model = None
        self._feature_names: list[str] = []

    def _compute_features(self, prices: list[float], volumes: list[float] | None = None) -> dict[str, float] | None:
        """Compute ML features from a price series (at least 60 data points)."""
        if len(prices) < 60:
            return None

        arr = np.array(prices, dtype=float)
        features: dict[str, float] = {}

        # Returns
        returns_1d = (arr[-1] - arr[-2]) / arr[-2] if arr[-2] != 0 else 0
        returns_5d = (arr[-1] - arr[-6]) / arr[-6] if len(arr) > 5 and arr[-6] != 0 else 0
        returns_10d = (arr[-1] - arr[-11]) / arr[-11] if len(arr) > 10 and arr[-11] != 0 else 0
        returns_20d = (arr[-1] - arr[-21]) / arr[-21] if len(arr) > 20 and arr[-21] != 0 else 0
        features["return_1d"] = returns_1d
        features["return_5d"] = returns_5d
        features["return_10d"] = returns_10d
        features["return_20d"] = returns_20d

        # Moving averages ratios
        ma5 = np.mean(arr[-5:])
        ma10 = np.mean(arr[-10:])
        ma20 = np.mean(arr[-20:])
        ma50 = np.mean(arr[-50:]) if len(arr) >= 50 else ma20
        features["price_to_ma5"] = arr[-1] / ma5 if ma5 != 0 else 1
        features["price_to_ma10"] = arr[-1] / ma10 if ma10 != 0 else 1
        features["price_to_ma20"] = arr[-1] / ma20 if ma20 != 0 else 1
        features["price_to_ma50"] = arr[-1] / ma50 if ma50 != 0 else 1
        features["ma5_to_ma20"] = ma5 / ma20 if ma20 != 0 else 1

        # Volatility
        daily_returns = np.diff(arr[-21:]) / arr[-21:-1]
        daily_returns = daily_returns[np.isfinite(daily_returns)]
        features["volatility_20d"] = float(np.std(daily_returns)) * np.sqrt(252) if len(daily_returns) > 1 else 0
        if len(arr) > 10:
            short_returns = np.diff(arr[-6:]) / arr[-6:-1]
            short_returns = short_returns[np.isfinite(short_returns)]
            features["volatility_5d"] = float(np.std(short_returns)) * np.sqrt(252) if len(short_returns) > 1 else 0
        else:
            features["volatility_5d"] = features["volatility_20d"]

        # RSI (14-period)
        deltas = np.diff(arr[-15:])
        gains = np.maximum(deltas, 0)
        losses = np.abs(np.minimum(deltas, 0))
        avg_gain = np.mean(gains) if len(gains) > 0 else 0
        avg_loss = np.mean(losses) if len(losses) > 0 else 0.001
        rs = avg_gain / avg_loss if avg_loss > 0 else 100
        features["rsi_14"] = 100 - (100 / (1 + rs))

        # MACD
        ema12 = self._ema(arr, 12)
        ema26 = self._ema(arr, 26)
        macd = ema12 - ema26
        features["macd"] = macd
        features["macd_pct"] = macd / arr[-1] if arr[-1] != 0 else 0

        # Bollinger Band position
        bb_std = np.std(arr[-20:])
        bb_upper = ma20 + 2 * bb_std
        bb_lower = ma20 - 2 * bb_std
        bb_range = bb_upper - bb_lower
        features["bb_position"] = (arr[-1] - bb_lower) / bb_range if bb_range > 0 else 0.5
        features["bb_width"] = bb_range / ma20 if ma20 != 0 else 0

        # Momentum
        features["momentum_5d"] = returns_5d
        features["momentum_20d"] = returns_20d

        # High-low range (last 20 days)
        high20 = np.max(arr[-20:])
        low20 = np.min(arr[-20:])
        features["range_position_20d"] = (arr[-1] - low20) / (high20 - low20) if high20 != low20 else 0.5

        # Volume features
        if volumes and len(volumes) >= 20:
            varr = np.array(volumes[-20:], dtype=float)
            avg_vol = np.mean(varr)
            features["volume_ratio"] = varr[-1] / avg_vol if avg_vol > 0 else 1
            features["volume_trend"] = np.mean(varr[-5:]) / avg_vol if avg_vol > 0 else 1
        else:
            features["volume_ratio"] = 1.0
            features["volume_trend"] = 1.0

        # Autocorrelation (mean reversion indicator)
        if len(daily_returns) > 5:
            features["autocorrelation"] = float(np.corrcoef(daily_returns[:-1], daily_returns[1:])[0, 1])
            if not np.isfinite(features["autocorrelation"]):
                features["autocorrelation"] = 0
        else:
            features["autocorrelation"] = 0

        return features

    @staticmethod
    def _ema(arr: np.ndarray, period: int) -> float:
        if len(arr) < period:
            return float(arr[-1])
        multiplier = 2 / (period + 1)
        ema = float(arr[-period])
        for price in arr[-period + 1:]:
            ema = (price - ema) * multiplier + ema
        return ema

    def _build_training_data(self, prices: list[float], volumes: list[float] | None = None,
                              forward_days: int = 5, threshold: float = 0.01) -> tuple:
        """Build feature matrix X and label vector y from historical prices.

        Labels: 0=SELL, 1=HOLD, 2=BUY based on forward return.
        """
        if len(prices) < 100:
            return None, None

        X_rows = []
        y_rows = []

        for i in range(60, len(prices) - forward_days):
            window = prices[:i + 1]
            vol_window = volumes[:i + 1] if volumes else None
            feats = self._compute_features(window, vol_window)
            if feats is None:
                continue

            # Forward return label
            future_price = prices[i + forward_days]
            current_price = prices[i]
            fwd_return = (future_price - current_price) / current_price if current_price != 0 else 0

            if fwd_return > threshold:
                label = 2  # BUY
            elif fwd_return < -threshold:
                label = 0  # SELL
            else:
                label = 1  # HOLD

            X_rows.append(list(feats.values()))
            y_rows.append(label)

        if not X_rows:
            return None, None

        self._feature_names = list(self._compute_features(prices[:61]).keys()) if len(prices) >= 61 else []
        return np.array(X_rows), np.array(y_rows)

    async def train_and_predict(self, symbol: str, prices: list[float] | None = None,
                                 volumes: list[float] | None = None) -> dict[str, Any]:
        """Train LightGBM on historical data and predict the current signal.

        If *prices* is not provided, fetches 6 months of data via yfinance.
        """
        if prices is None:
            prices, volumes = await self._fetch_prices(symbol)
            if prices is None:
                return {"symbol": symbol, "error": "Could not fetch price history", "ml_available": False}

        if not _ensure_lgb():
            return await self._rule_based_predict(symbol, prices, volumes)

        if len(prices) < 100:
            return {
                "symbol": symbol,
                "error": "Insufficient data for ML prediction (need 100+ price points)",
                "ml_available": False,
            }

        try:
            result = await asyncio.to_thread(
                self._train_and_predict_sync, symbol, prices, volumes
            )
            return result
        except Exception as e:
            logger.error("ML prediction failed for %s: %s", symbol, e)
            return await self._rule_based_predict(symbol, prices, volumes)

    def _train_and_predict_sync(self, symbol: str, prices: list[float],
                                 volumes: list[float] | None) -> dict[str, Any]:
        X, y = self._build_training_data(prices, volumes)
        if X is None or len(X) < 30:
            return {
                "symbol": symbol,
                "error": "Not enough training samples",
                "ml_available": False,
            }

        # Train/test split (last 20% for validation)
        split = int(len(X) * 0.8)
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]

        train_data = _lgb.Dataset(X_train, label=y_train)
        valid_data = _lgb.Dataset(X_test, label=y_test, reference=train_data)

        params = {
            "objective": "multiclass",
            "num_class": 3,
            "metric": "multi_logloss",
            "boosting_type": "gbdt",
            "num_leaves": 31,
            "learning_rate": 0.05,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "verbose": -1,
            "seed": 42,
        }

        callbacks = [_lgb.log_evaluation(period=0)]
        model = _lgb.train(
            params,
            train_data,
            num_boost_round=200,
            valid_sets=[valid_data],
            callbacks=callbacks + [_lgb.early_stopping(stopping_rounds=20)],
        )
        self._model = model

        # Predict current
        current_features = self._compute_features(prices, volumes)
        if current_features is None:
            return {"symbol": symbol, "error": "Could not compute current features", "ml_available": False}

        X_current = np.array([list(current_features.values())])
        probs = model.predict(X_current)[0]  # [sell_prob, hold_prob, buy_prob]

        # Validation accuracy
        y_pred_test = model.predict(X_test)
        y_pred_labels = np.argmax(y_pred_test, axis=1)
        accuracy = float(np.mean(y_pred_labels == y_test))

        # Feature importance
        importance = model.feature_importance(importance_type="gain")
        feat_importance = {}
        if self._feature_names and len(self._feature_names) == len(importance):
            for name, imp in sorted(zip(self._feature_names, importance), key=lambda x: -x[1]):
                feat_importance[name] = float(imp)

        # Convert to signal
        action_idx = int(np.argmax(probs))
        actions = ["SELL", "HOLD", "BUY"]
        action = actions[action_idx]
        confidence = float(probs[action_idx])

        return {
            "symbol": symbol,
            "ml_available": True,
            "action": action,
            "confidence": confidence,
            "probabilities": {
                "sell": float(probs[0]),
                "hold": float(probs[1]),
                "buy": float(probs[2]),
            },
            "validation_accuracy": accuracy,
            "training_samples": len(X_train),
            "test_samples": len(X_test),
            "feature_importance": dict(list(feat_importance.items())[:10]),
            "model_type": "LightGBM",
        }

    @staticmethod
    async def _fetch_prices(symbol: str) -> tuple[list[float] | None, list[float] | None]:
        """Fetch 6 months of daily close prices via yfinance."""
        try:
            import yfinance as yf

            def _download():
                tk = yf.Ticker(symbol)
                df = tk.history(period="6mo", interval="1d")
                if df.empty:
                    return None, None
                closes = df["Close"].dropna().tolist()
                volumes = df["Volume"].dropna().tolist() if "Volume" in df.columns else None
                return closes, volumes

            return await asyncio.to_thread(_download)
        except Exception as exc:
            logger.warning("Failed to fetch prices for %s: %s", symbol, exc)
            return None, None

    async def _rule_based_predict(self, symbol: str, prices: list[float],
                                   volumes: list[float] | None) -> dict[str, Any]:
        """Fallback rule-based prediction when LightGBM is not available."""
        if len(prices) < 20:
            return {"symbol": symbol, "error": "Insufficient data", "ml_available": False}

        features = self._compute_features(prices, volumes)
        if features is None:
            return {"symbol": symbol, "error": "Could not compute features", "ml_available": False}

        # Simple scoring
        score = 0
        reasons = []

        rsi = features.get("rsi_14", 50)
        if rsi < 30:
            score += 2
            reasons.append(f"RSI oversold ({rsi:.1f})")
        elif rsi > 70:
            score -= 2
            reasons.append(f"RSI overbought ({rsi:.1f})")

        if features.get("price_to_ma20", 1) > 1.02:
            score += 1
            reasons.append("Price above MA20")
        elif features.get("price_to_ma20", 1) < 0.98:
            score -= 1
            reasons.append("Price below MA20")

        if features.get("macd", 0) > 0:
            score += 1
            reasons.append("MACD positive")
        else:
            score -= 1
            reasons.append("MACD negative")

        momentum = features.get("momentum_5d", 0)
        if momentum > 0.02:
            score += 1
            reasons.append(f"Positive momentum ({momentum:.2%})")
        elif momentum < -0.02:
            score -= 1
            reasons.append(f"Negative momentum ({momentum:.2%})")

        if score >= 2:
            action = "BUY"
            confidence = min(0.5 + score * 0.1, 0.85)
        elif score <= -2:
            action = "SELL"
            confidence = min(0.5 + abs(score) * 0.1, 0.85)
        else:
            action = "HOLD"
            confidence = 0.5

        return {
            "symbol": symbol,
            "ml_available": False,
            "action": action,
            "confidence": confidence,
            "probabilities": {
                "sell": 0.33 if action == "HOLD" else (0.8 if action == "SELL" else 0.1),
                "hold": 0.34 if action == "HOLD" else 0.1,
                "buy": 0.33 if action == "HOLD" else (0.8 if action == "BUY" else 0.1),
            },
            "model_type": "rule_based_fallback",
            "reasons": reasons,
            "features": features,
        }
