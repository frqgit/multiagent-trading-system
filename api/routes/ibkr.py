"""IBKR routes — Interactive Brokers connection, market data, orders, positions."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from core.auth import get_current_user
from memory.db import log_audit, save_trade

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ibkr", tags=["ibkr"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class IBKROrderRequest(BaseModel):
    symbol: str = Field(..., description="Stock symbol")
    action: str = Field(..., pattern="^(BUY|SELL)$")
    quantity: int = Field(..., gt=0)
    order_type: str = Field("MKT", description="MKT, LMT, STP, STP_LMT")
    limit_price: float | None = None
    stop_price: float | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_client():
    from tools.ibkr_client import get_ibkr_client
    return get_ibkr_client()


async def _require_enterprise(authorization: str | None) -> dict:
    user = await get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if user["tier"] not in ("enterprise", "pro") and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="IBKR features require Pro or Enterprise tier")
    return user


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/status")
async def ibkr_status(authorization: str = Header(None)):
    """Check IBKR connection status and config."""
    await _require_enterprise(authorization)
    client = _get_client()

    from core.config import get_settings
    settings = get_settings()

    return {
        "connected": client.connected,
        "mode": settings.ibkr_mode,
        "host": settings.ibkr_host,
        "port": settings.ibkr_port,
        "available": settings.ibkr_available,
    }


@router.post("/connect")
async def ibkr_connect(authorization: str = Header(None)):
    """Connect to IBKR TWS/Gateway."""
    user = await _require_enterprise(authorization)
    client = _get_client()

    result = await client.connect()
    await log_audit("ibkr_connect", user_id=user["id"], details=result)
    return result


@router.post("/disconnect")
async def ibkr_disconnect(authorization: str = Header(None)):
    """Disconnect from IBKR."""
    user = await _require_enterprise(authorization)
    client = _get_client()

    result = await client.disconnect()
    await log_audit("ibkr_disconnect", user_id=user["id"])
    return result


@router.get("/market-data/{symbol}")
async def ibkr_market_data(symbol: str, authorization: str = Header(None)):
    """Get live market data from IBKR."""
    await _require_enterprise(authorization)
    client = _get_client()

    data = await client.get_market_data(symbol)
    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"])
    return data


@router.get("/historical/{symbol}")
async def ibkr_historical_data(
    symbol: str, duration: str = "1 M", bar_size: str = "1 day",
    authorization: str = Header(None),
):
    """Get historical data from IBKR."""
    await _require_enterprise(authorization)
    client = _get_client()

    data = await client.get_historical_data(symbol, duration=duration, bar_size=bar_size)
    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"])
    return data


@router.post("/order")
async def ibkr_place_order(req: IBKROrderRequest, authorization: str = Header(None)):
    """Place an order via IBKR."""
    user = await _require_enterprise(authorization)

    # Risk check
    from agents.risk_agent import RiskManagerAgent
    risk_agent = RiskManagerAgent()
    if risk_agent.is_trading_halted:
        raise HTTPException(status_code=403, detail="Trading is halted due to daily loss limit")

    client = _get_client()
    result = await client.place_order(
        symbol=req.symbol,
        action=req.action,
        quantity=req.quantity,
        order_type=req.order_type,
        limit_price=req.limit_price,
        stop_price=req.stop_price,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    # Audit log + trade record
    await log_audit("ibkr_order", user_id=user["id"], details={
        "symbol": req.symbol, "action": req.action, "quantity": req.quantity,
        "order_type": req.order_type, "result": result,
    })
    await save_trade(
        user_id=user["id"],
        symbol=req.symbol,
        action=req.action,
        quantity=req.quantity,
        price=req.limit_price or 0,
        order_type=req.order_type,
        mode="paper" if _get_ibkr_mode() == "paper" else "live",
        broker="ibkr",
    )

    return result


@router.get("/positions")
async def ibkr_positions(authorization: str = Header(None)):
    """Get current IBKR positions."""
    await _require_enterprise(authorization)
    client = _get_client()

    positions = await client.get_positions()
    return {"positions": positions}


@router.get("/account")
async def ibkr_account(authorization: str = Header(None)):
    """Get IBKR account summary."""
    await _require_enterprise(authorization)
    client = _get_client()

    summary = await client.get_account_summary()
    return summary


@router.get("/orders")
async def ibkr_open_orders(authorization: str = Header(None)):
    """Get open orders from IBKR."""
    await _require_enterprise(authorization)
    client = _get_client()

    orders = await client.get_open_orders()
    return {"orders": orders}


@router.delete("/order/{order_id}")
async def ibkr_cancel_order(order_id: int, authorization: str = Header(None)):
    """Cancel an IBKR order."""
    user = await _require_enterprise(authorization)
    client = _get_client()

    result = await client.cancel_order(order_id)
    await log_audit("ibkr_cancel_order", user_id=user["id"], details={"order_id": order_id})
    return result


@router.get("/pnl")
async def ibkr_pnl(authorization: str = Header(None)):
    """Get IBKR P&L data."""
    await _require_enterprise(authorization)
    client = _get_client()

    pnl = await client.get_pnl()
    return pnl


def _get_ibkr_mode() -> str:
    try:
        from core.config import get_settings
        return get_settings().ibkr_mode
    except Exception:
        return "paper"
