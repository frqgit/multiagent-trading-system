"""API route for stock analysis — the main endpoint."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from agents.orchestrator import OrchestratorAgent
from core.auth import FREE_TIER_PROMPT_LIMIT, TIER_PROMPT_LIMITS, get_current_user
from memory.db import User, _get_session_factory, save_analysis, get_history
from memory.vector_store import vector_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["analysis"])

orchestrator = OrchestratorAgent()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------
class AnalyzeRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500, description="User query, e.g. 'Analyze AAPL'")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000, description="Any financial question or stock query")


class NewsArticle(BaseModel):
    title: str
    description: str | None = None
    source: str | None = None
    url: str | None = None
    published: str | None = None


class MarketDataResponse(BaseModel):
    price: float | None = None
    trend: str | None = None
    ma20: float | None = None
    ma50: float | None = None
    ma200: float | None = None
    ema12: float | None = None
    ema26: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    rsi: float | None = None
    volatility: float | None = None
    volume: int | None = None
    avg_volume: int | None = None
    price_change_pct: float | None = None
    company_name: str | None = None
    sector: str | None = None
    market_cap_formatted: str | None = None
    pe_ratio: float | None = None
    eps: float | None = None
    dividend_yield: float | None = None
    beta: float | None = None
    week52_high: float | None = None
    week52_low: float | None = None
    signals: list[str] = []
    price_history_30d: list[dict] = []


class SentimentResponse(BaseModel):
    sentiment: str = "neutral"
    confidence: float = 0.0
    impact_level: str = "low"
    key_themes: list[str] = []
    catalysts: list[str] = []
    media_tone: str | None = None
    momentum_shift: str | None = None
    institutional_signals: list[str] = []
    reasoning: str | None = None


class RiskResponse(BaseModel):
    risk_score: int = 0
    risk_level: str = "unknown"
    warnings: list[str] = []
    constraints: list[str] = []
    allow_buy: bool = True


class PriceTargetRange(BaseModel):
    low: float | None = None
    high: float | None = None


class ResearchResponse(BaseModel):
    analyst_consensus: str = "unknown"
    average_price_target: float | None = None
    price_target_range: PriceTargetRange = PriceTargetRange()
    recent_earnings_surprise: str = "unknown"
    revenue_trend: str = "unknown"
    key_developments: list[str] = []
    competitive_position: str = "unknown"
    insider_activity: str = "unknown"
    risks_from_research: list[str] = []
    opportunities_from_research: list[str] = []
    institutional_ownership_trend: str = "unknown"
    short_interest_signal: str = "unknown"
    catalyst_timeline: list[str] = []
    research_summary: str = ""
    sources_searched: int = 0
    pages_analyzed: int = 0


class DecisionResponse(BaseModel):
    action: str = "HOLD"
    confidence: float = 0.0
    reasoning: str = ""
    key_factors: list[str] = []
    risk_adjusted: bool = False
    suggested_entry: float | None = None
    suggested_stop_loss: float | None = None
    target_price: float | None = None
    time_horizon: str | None = None
    macro_alignment: str | None = None
    position_size_recommendation: str | None = None


class AnalyzeResponse(BaseModel):
    symbol: str
    decision: DecisionResponse
    market_data: MarketDataResponse
    news_articles: list[NewsArticle] = []
    news_article_count: int = 0
    sentiment: SentimentResponse
    risk: RiskResponse
    research: ResearchResponse = ResearchResponse()
    elapsed_seconds: float


class HistoryResponse(BaseModel):
    records: list[dict]


class HealthResponse(BaseModel):
    status: str
    vector_store_count: int
    llm_ready: bool = False
    news_ready: bool = False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/analyze", response_model=list[AnalyzeResponse])
async def analyze(req: AnalyzeRequest):
    """Analyze one or more stock symbols from natural language input."""
    symbols = orchestrator.parse_symbols(req.message)
    if not symbols:
        raise HTTPException(
            status_code=400,
            detail="Could not identify any stock symbols. Try something like 'Analyze AAPL MSFT'.",
        )
    if len(symbols) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 symbols per request.")

    results = await orchestrator.analyze_multiple(symbols)

    responses: list[AnalyzeResponse] = []
    for r in results:
        # Persist
        try:
            await save_analysis(r)
            await vector_store.store_analysis(r)
        except Exception:
            pass

        decision_raw = r.get("decision", {})
        risk_raw = r.get("risk", {})
        sentiment_raw = r.get("sentiment", {})
        market_raw = r.get("market_data", {})
        news_raw = r.get("news", {})
        research_raw = r.get("research", {})

        articles = [
            NewsArticle(
                title=a.get("title", ""),
                description=a.get("description"),
                source=a.get("source"),
                url=a.get("url"),
                published=a.get("published"),
            )
            for a in news_raw.get("articles", [])
        ]

        responses.append(AnalyzeResponse(
            symbol=r.get("symbol", ""),
            decision=DecisionResponse(**{k: v for k, v in decision_raw.items() if k in DecisionResponse.model_fields}),
            market_data=MarketDataResponse(**{k: v for k, v in market_raw.items() if k in MarketDataResponse.model_fields}),
            news_articles=articles,
            news_article_count=news_raw.get("article_count", len(articles)),
            sentiment=SentimentResponse(**{k: v for k, v in sentiment_raw.items() if k in SentimentResponse.model_fields}),
            risk=RiskResponse(**{k: v for k, v in risk_raw.items() if k in RiskResponse.model_fields}),
            research=ResearchResponse(**{k: v for k, v in research_raw.items() if k in ResearchResponse.model_fields}),
            elapsed_seconds=r.get("elapsed_seconds", 0),
        ))

    return responses


@router.get("/history", response_model=HistoryResponse)
async def history(symbol: str | None = None, limit: int = 20):
    """Retrieve past analysis records."""
    records = await get_history(symbol=symbol, limit=min(limit, 100))
    return HistoryResponse(records=records)


@router.get("/health", response_model=HealthResponse)
async def health():
    from core.config import get_settings
    try:
        settings = get_settings()
        llm_ok = bool(settings.openai_api_key and not settings.openai_api_key.startswith("sk-your"))
        news_ok = bool(settings.news_api_key and settings.news_api_key != "your-newsapi-key-here")
    except Exception:
        llm_ok = False
        news_ok = False
    return HealthResponse(
        status="ok",
        vector_store_count=vector_store.count(),
        llm_ready=llm_ok,
        news_ready=news_ok,
    )


@router.post("/search-memory")
async def search_memory(query: str):
    """Semantic search over past analyses stored in vector memory."""
    results = await vector_store.search(query, top_k=5)
    return {"results": results}


@router.post("/chat")
async def chat(req: ChatRequest, authorization: str = Header(None)):
    """OpenClaw-style natural language endpoint — understands any financial query.

    Requires authentication. Free tier: 3 prompts. Paid tier: $10 credit with
    token usage deductions.

    Returns a flexible response with:
    - answer: markdown-formatted text response
    - type: the detected intent (quick_status, full_analysis, general_question, etc.)
    - data: structured data (market_data, analyses, articles, etc.) depending on type
    """
    # ── Auth enforcement ──
    user = await get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required. Please log in.")
    if not user["is_approved"]:
        raise HTTPException(status_code=403, detail="Your account is pending admin approval.")

    # Tier limits
    tier = user["tier"]
    prompt_limit = TIER_PROMPT_LIMITS.get(tier, FREE_TIER_PROMPT_LIMIT)
    if prompt_limit >= 0 and user["prompt_count"] >= prompt_limit:
        raise HTTPException(
            status_code=403,
            detail=f"{tier.title()} tier limit reached ({prompt_limit} prompts). Upgrade for continued access.",
        )

    result = await orchestrator.chat(req.message)

    # ── Update user usage in DB ──
    # Wrapped in try/catch so a transient DB failure doesn't discard
    # the orchestrator's response the user is waiting for.
    try:
        prompt_cost = result.get("token_usage", {}).get("cost_usd", 0)
        factory = _get_session_factory()
        async with factory() as session:
            db_result = await session.execute(select(User).where(User.id == user["id"]))
            db_user = db_result.scalar_one_or_none()
            if db_user:
                db_user.prompt_count += 1
                db_user.total_cost_usd = float(db_user.total_cost_usd) + prompt_cost
                if db_user.tier == "paid":
                    db_user.balance_usd = max(0, float(db_user.balance_usd) - prompt_cost)
                await session.commit()
    except Exception as db_exc:
        logger.error("Failed to update user usage after chat: %s", db_exc)

    response: dict = {
        "answer": result.get("answer", ""),
        "type": result.get("type", "unknown"),
        "intent": result.get("intent", "unknown"),
        "symbols": result.get("parsed_symbols", result.get("symbols", [])),
        "elapsed_seconds": result.get("elapsed_seconds", 0),
        "token_usage": result.get("token_usage", {}),
    }

    # Attach structured data based on response type
    resp_type = result.get("type", "")
    if resp_type == "full_analysis":
        analyses = result.get("analyses", [])
        formatted = []
        for r in analyses:
            try:
                await save_analysis(r)
                await vector_store.store_analysis(r)
            except Exception:
                pass

            decision_raw = r.get("decision", {})
            risk_raw = r.get("risk", {})
            sentiment_raw = r.get("sentiment", {})
            market_raw = r.get("market_data", {})
            news_raw = r.get("news", {})
            research_raw = r.get("research", {})

            articles = [
                {
                    "title": a.get("title", ""),
                    "description": a.get("description"),
                    "source": a.get("source"),
                    "url": a.get("url"),
                    "published": a.get("published"),
                }
                for a in news_raw.get("articles", [])
            ]

            formatted.append({
                "symbol": r.get("symbol", ""),
                "decision": {k: v for k, v in decision_raw.items() if k in DecisionResponse.model_fields},
                "market_data": {k: v for k, v in market_raw.items() if k in MarketDataResponse.model_fields},
                "news_articles": articles,
                "news_article_count": news_raw.get("article_count", len(articles)),
                "sentiment": {k: v for k, v in sentiment_raw.items() if k in SentimentResponse.model_fields},
                "risk": {k: v for k, v in risk_raw.items() if k in RiskResponse.model_fields},
                "research": {k: v for k, v in research_raw.items() if k in ResearchResponse.model_fields},
                "elapsed_seconds": r.get("elapsed_seconds", 0),
            })
        response["analyses"] = formatted
        response["global_macro"] = result.get("global_macro", {})
    elif resp_type == "quick_status":
        response["market_data"] = result.get("market_data", [])
    elif resp_type == "comparison":
        response["market_data"] = result.get("market_data", [])
    elif resp_type == "news_query":
        response["articles"] = result.get("articles", [])
    elif resp_type == "global_outlook":
        response["global_macro"] = result.get("global_macro", {})
        response["market_data"] = result.get("market_data", [])
    elif resp_type == "general_question":
        response["search_results"] = result.get("search_results", [])

    return response
