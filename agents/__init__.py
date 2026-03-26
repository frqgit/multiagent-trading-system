"""Multi-agent trading system agents.

Core Agents:
- MarketAnalystAgent: Real-time market data analysis
- NewsAnalystAgent: News aggregation and analysis
- SentimentAgent: Sentiment analysis from news
- RiskManagerAgent: Risk assessment and constraints
- DecisionAgent: Trading decision synthesis
- ResearchAgent: Web research for stocks
- GlobalMarketAdvisorAgent: Macro and global market analysis
- OrchestratorAgent: Central coordinator

Advanced Agents:
- PortfolioOptimizationAgent: MPT, Black-Litterman, Risk Parity
- BacktestingAgent: Strategy backtesting with walk-forward
- VolatilityModelingAgent: GARCH, EWMA, regime detection
- TechnicalStrategyAgent: Multi-strategy technical analysis
- CorrelationAnalysisAgent: Correlation and pair trading
- AdaptiveLearningAgent: ML-based strategy adaptation
- ExecutionAgent: Paper trading execution
"""

from agents.market_agent import MarketAnalystAgent
from agents.news_agent import NewsAnalystAgent
from agents.sentiment_agent import SentimentAgent
from agents.risk_agent import RiskManagerAgent
from agents.decision_agent import DecisionAgent
from agents.research_agent import ResearchAgent
from agents.global_market_agent import GlobalMarketAdvisorAgent
from agents.orchestrator import OrchestratorAgent

# Advanced agents
from agents.portfolio_agent import PortfolioOptimizationAgent
from agents.backtest_agent import BacktestingAgent
from agents.volatility_agent import VolatilityModelingAgent
from agents.technical_strategy_agent import TechnicalStrategyAgent
from agents.correlation_agent import CorrelationAnalysisAgent
from agents.adaptive_agent import AdaptiveLearningAgent
from agents.execution_agent import ExecutionAgent

__all__ = [
    # Core
    "MarketAnalystAgent",
    "NewsAnalystAgent",
    "SentimentAgent",
    "RiskManagerAgent",
    "DecisionAgent",
    "ResearchAgent",
    "GlobalMarketAdvisorAgent",
    "OrchestratorAgent",
    # Advanced
    "PortfolioOptimizationAgent",
    "BacktestingAgent",
    "VolatilityModelingAgent",
    "TechnicalStrategyAgent",
    "CorrelationAnalysisAgent",
    "AdaptiveLearningAgent",
    "ExecutionAgent",
]
