"""Tests for the Orchestrator Agent symbol parsing."""

from __future__ import annotations

from agents.orchestrator import OrchestratorAgent


def test_parse_single_symbol():
    symbols = OrchestratorAgent.parse_symbols("Analyze AAPL")
    assert symbols == ["AAPL"]


def test_parse_multiple_symbols():
    symbols = OrchestratorAgent.parse_symbols("What do you think about AAPL and MSFT?")
    assert "AAPL" in symbols
    assert "MSFT" in symbols


def test_parse_filters_stop_words():
    symbols = OrchestratorAgent.parse_symbols("Should I BUY TSLA or SELL NVDA?")
    assert "BUY" not in symbols
    assert "SELL" not in symbols
    assert "TSLA" in symbols
    assert "NVDA" in symbols


def test_parse_no_symbols():
    symbols = OrchestratorAgent.parse_symbols("Hello, how are you?")
    assert symbols == []


def test_parse_deduplicates():
    symbols = OrchestratorAgent.parse_symbols("AAPL AAPL AAPL")
    assert symbols == ["AAPL"]
