"""Strategy Builder routes — CRUD for user strategies + backtest."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from core.auth import get_current_user
from memory.db import (
    _get_session_factory,
    UserStrategy,
    get_user_strategies,
    save_user_strategy,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CreateStrategyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    strategy_type: str = Field(..., description="Type: ma_crossover, rsi_mean_reversion, bollinger_breakout, macd_signal, momentum_trend, combined_multi_indicator")
    parameters: dict = Field(default_factory=dict)
    description: str = ""


class BacktestStrategyRequest(BaseModel):
    strategy_type: str
    parameters: dict = Field(default_factory=dict)
    symbol: str = Field(..., description="Stock symbol to backtest against")
    initial_capital: float = Field(100000, gt=0)


class UpdateStrategyRequest(BaseModel):
    name: str | None = None
    parameters: dict | None = None
    description: str | None = None
    is_active: bool | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/templates")
async def list_templates():
    """List available strategy templates."""
    from agents.strategy_builder import STRATEGY_TEMPLATES
    return {"templates": STRATEGY_TEMPLATES}


@router.get("/")
async def list_strategies(authorization: str = Header(None)):
    """List all strategies for the authenticated user."""
    user = await get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    strategies = await get_user_strategies(user["id"])
    return {"strategies": strategies}


@router.post("/")
async def create_strategy(req: CreateStrategyRequest, authorization: str = Header(None)):
    """Create and validate a new strategy."""
    user = await get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    from agents.strategy_builder import StrategyBuilderAgent
    builder = StrategyBuilderAgent()

    result = await builder.build_strategy(
        name=req.name,
        strategy_type=req.strategy_type,
        parameters=req.parameters,
        user_id=user["id"],
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    strategy_id = await save_user_strategy(
        user_id=user["id"],
        name=req.name,
        strategy_type=req.strategy_type,
        parameters=result["parameters"],
        description=req.description,
    )

    return {
        "id": strategy_id,
        "strategy": result,
        "message": "Strategy created successfully",
    }


@router.put("/{strategy_id}")
async def update_strategy(
    strategy_id: str,
    req: UpdateStrategyRequest,
    authorization: str = Header(None),
):
    """Update an existing strategy."""
    user = await get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    from sqlalchemy import select

    factory = _get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(UserStrategy).where(
                UserStrategy.id == strategy_id,
                UserStrategy.user_id == user["id"],
            )
        )
        strategy = result.scalar_one_or_none()
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")

        if req.name is not None:
            strategy.name = req.name
        if req.parameters is not None:
            strategy.parameters = req.parameters
        if req.description is not None:
            strategy.description = req.description
        if req.is_active is not None:
            strategy.is_active = req.is_active

        await session.commit()
        return {"message": "Strategy updated"}


@router.delete("/{strategy_id}")
async def delete_strategy(strategy_id: str, authorization: str = Header(None)):
    """Delete a strategy."""
    user = await get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    from sqlalchemy import select

    factory = _get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(UserStrategy).where(
                UserStrategy.id == strategy_id,
                UserStrategy.user_id == user["id"],
            )
        )
        strategy = result.scalar_one_or_none()
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")

        await session.delete(strategy)
        await session.commit()
        return {"message": "Strategy deleted"}


@router.post("/backtest")
async def backtest_strategy(req: BacktestStrategyRequest, authorization: str = Header(None)):
    """Backtest a strategy on historical data."""
    user = await get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Fetch historical prices
    import asyncio
    from tools.stock_api import fetch_stock_data

    try:
        snapshot = await asyncio.to_thread(fetch_stock_data, req.symbol)
        prices = snapshot.price_history_30d
        if not prices or len(prices) < 60:
            raise HTTPException(status_code=400, detail="Insufficient price data for backtesting (need 60+ data points)")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not fetch data for {req.symbol}: {e}")

    from agents.strategy_builder import StrategyBuilderAgent
    builder = StrategyBuilderAgent()

    result = await builder.backtest_custom_strategy(
        symbol=req.symbol,
        strategy_type=req.strategy_type,
        parameters=req.parameters,
        prices=prices,
        initial_capital=req.initial_capital,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return {"backtest_results": result}
