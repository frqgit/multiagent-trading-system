"""Tests for the Risk Manager Agent."""

from __future__ import annotations

import pytest
from agents.risk_agent import RiskManagerAgent


@pytest.fixture
def risk_agent():
    return RiskManagerAgent()


@pytest.mark.asyncio
async def test_low_risk_scenario(risk_agent):
    market = {"symbol": "AAPL", "rsi": 50, "volatility": 15, "trend": "bullish", "price_change_pct": 1.0}
    sentiment = {"sentiment": "positive", "impact_level": "low"}
    result = await risk_agent.analyze(market, sentiment)
    assert result["risk_level"] == "low"
    assert result["allow_buy"] is True


@pytest.mark.asyncio
async def test_high_risk_scenario(risk_agent):
    market = {"symbol": "TSLA", "rsi": 85, "volatility": 55, "trend": "bearish", "price_change_pct": -8.0}
    sentiment = {"sentiment": "negative", "impact_level": "high"}
    result = await risk_agent.analyze(market, sentiment)
    assert result["risk_level"] == "high"
    assert result["risk_score"] >= 7


@pytest.mark.asyncio
async def test_overbought_warning(risk_agent):
    market = {"symbol": "TEST", "rsi": 75, "volatility": 10, "trend": "bullish", "price_change_pct": 0}
    sentiment = {"sentiment": "neutral", "impact_level": "low"}
    result = await risk_agent.analyze(market, sentiment)
    assert any("overbought" in w.lower() for w in result["warnings"])
