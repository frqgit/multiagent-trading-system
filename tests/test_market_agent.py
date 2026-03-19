"""Tests for the Market Analyst Agent and stock tools."""

from __future__ import annotations

import pytest
from tools.stock_api import fetch_stock_data, _compute_rsi, _detect_trend
import numpy as np


def test_compute_rsi_neutral():
    prices = np.array([100.0 + i * 0.1 for i in range(20)])
    rsi = _compute_rsi(prices, period=14)
    assert 0.0 <= rsi <= 100.0


def test_compute_rsi_all_gains():
    prices = np.array([float(i) for i in range(1, 20)])
    rsi = _compute_rsi(prices, period=14)
    assert rsi == 100.0


def test_compute_rsi_short_series():
    prices = np.array([100.0, 101.0, 99.0])
    rsi = _compute_rsi(prices, period=14)
    assert rsi == 50.0  # default for short series


def test_detect_trend_bullish():
    assert _detect_trend(ma20=150.0, ma50=140.0, current=160.0) == "bullish"


def test_detect_trend_bearish():
    assert _detect_trend(ma20=130.0, ma50=140.0, current=120.0) == "bearish"


def test_detect_trend_sideways():
    assert _detect_trend(ma20=150.0, ma50=140.0, current=145.0) == "sideways"


def test_fetch_stock_data_valid():
    """Integration test — requires internet."""
    snapshot = fetch_stock_data("AAPL", period="5d")
    assert snapshot.symbol == "AAPL"
    assert snapshot.current_price > 0
    assert 0 <= snapshot.rsi <= 100
    assert snapshot.trend in ("bullish", "bearish", "sideways")


def test_fetch_stock_data_invalid():
    with pytest.raises(ValueError, match="No data returned"):
        fetch_stock_data("ZZZZZZZZZ", period="5d")
