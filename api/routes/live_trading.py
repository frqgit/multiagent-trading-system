"""Multi-broker trading routes — enterprise order execution, portfolio, risk, compliance.

Provides REST API for:
- Multi-broker connection management
- Order submission through risk-gated OMS
- Portfolio views (per-broker and consolidated)
- Risk engine status and controls
- Compliance monitoring
- Kill switch / emergency controls
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from core.auth import get_current_user
from memory.db import log_audit, save_trade

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/trading", tags=["trading-live"])


# ── Schemas ────────────────────────────────────────────────────────────────

class LiveOrderRequest(BaseModel):
    symbol: str = Field(..., description="Stock symbol (e.g., CBA, BHP, AAPL)")
    side: str = Field(..., pattern="^(BUY|SELL)$")
    quantity: int = Field(..., gt=0, le=100000)
    order_type: str = Field("MKT", description="MKT, LMT, STP, STP_LMT, TRAIL")
    price: float | None = Field(None, description="Limit price")
    stop_price: float | None = Field(None, description="Stop trigger price")
    trail_percent: float | None = Field(None, description="Trailing stop %")
    take_profit: float | None = Field(None, description="Take-profit price")
    stop_loss: float | None = Field(None, description="Stop-loss price")
    exchange: str = Field("ASX", description="Target exchange")
    currency: str = Field("AUD", description="Currency code")
    preferred_broker: str | None = Field(None, description="Broker ID to route to")


class BracketOrderRequest(BaseModel):
    symbol: str
    side: str = Field(..., pattern="^(BUY|SELL)$")
    quantity: int = Field(..., gt=0)
    entry_price: float | None = None
    take_profit: float = Field(..., gt=0)
    stop_loss: float = Field(..., gt=0)
    exchange: str = "ASX"
    currency: str = "AUD"
    preferred_broker: str | None = None


class SignalExecutionRequest(BaseModel):
    symbol: str
    action: str = Field(..., description="STRONG_BUY, BUY, SELL, STRONG_SELL")
    confidence: float = Field(..., ge=0, le=1)
    entry_price: float | None = None
    stop_loss: float | None = None
    target_price: float | None = None
    position_size_recommendation: int | None = None
    exchange: str = "ASX"
    currency: str = "AUD"
    preferred_broker: str | None = None


# ── Auth Helper ────────────────────────────────────────────────────────────

async def _require_trading_access(authorization: str | None) -> dict:
    user = await get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if user["tier"] not in ("enterprise", "pro") and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Live trading requires Pro or Enterprise tier")
    return user


# ── Broker Management ─────────────────────────────────────────────────────

@router.get("/brokers")
async def list_brokers(authorization: str = Header(None)):
    """List all registered brokers and their connection status."""
    await _require_trading_access(authorization)
    from tools.broker_manager import get_broker_manager
    manager = get_broker_manager()
    return {"brokers": manager.list_brokers()}


@router.post("/brokers/connect")
async def connect_brokers(authorization: str = Header(None)):
    """Connect to all configured brokers."""
    user = await _require_trading_access(authorization)
    from tools.broker_manager import get_broker_manager
    manager = get_broker_manager()
    results = await manager.connect_all()
    await log_audit("brokers_connect", user_id=user["id"], details=results)
    return {"results": results}


@router.post("/brokers/{broker_id}/connect")
async def connect_broker(broker_id: str, authorization: str = Header(None)):
    """Connect to a specific broker."""
    user = await _require_trading_access(authorization)
    from tools.broker_manager import get_broker_manager
    manager = get_broker_manager()
    broker = manager.get_broker(broker_id)
    if not broker:
        raise HTTPException(status_code=404, detail=f"Broker {broker_id} not registered")
    result = await broker.connect()
    await log_audit("broker_connect", user_id=user["id"],
                    details={"broker": broker_id, "success": result})
    return {"broker": broker_id, "connected": result}


@router.get("/brokers/health")
async def broker_health(authorization: str = Header(None)):
    """Health check all brokers."""
    await _require_trading_access(authorization)
    from tools.broker_manager import get_broker_manager
    manager = get_broker_manager()
    return await manager.health_check_all()


# ── Order Execution ───────────────────────────────────────────────────────

@router.post("/orders")
async def submit_order(req: LiveOrderRequest, authorization: str = Header(None)):
    """Submit a live order through the risk-gated OMS."""
    user = await _require_trading_access(authorization)

    from core.order_management import get_oms
    oms = get_oms()

    result = await oms.submit_order(
        symbol=req.symbol,
        side=req.side,
        quantity=req.quantity,
        order_type=req.order_type,
        price=req.price,
        stop_price=req.stop_price,
        trail_percent=req.trail_percent,
        take_profit=req.take_profit,
        stop_loss=req.stop_loss,
        exchange=req.exchange,
        currency=req.currency,
        preferred_broker=req.preferred_broker,
        user_id=str(user["id"]),
    )

    if result.get("success"):
        await save_trade(
            user_id=user["id"],
            symbol=req.symbol,
            action=req.side,
            quantity=req.quantity,
            price=result.get("avg_fill_price", req.price or 0),
            order_type=req.order_type,
            mode="live",
            broker=result.get("broker", ""),
        )
    await log_audit("live_order", user_id=user["id"], details=result)
    return result


@router.post("/orders/bracket")
async def submit_bracket_order(req: BracketOrderRequest, authorization: str = Header(None)):
    """Submit a bracket order (entry + take-profit + stop-loss)."""
    user = await _require_trading_access(authorization)

    from core.order_management import get_oms
    oms = get_oms()

    result = await oms.submit_bracket_order(
        symbol=req.symbol,
        side=req.side,
        quantity=req.quantity,
        entry_price=req.entry_price,
        take_profit=req.take_profit,
        stop_loss=req.stop_loss,
        exchange=req.exchange,
        currency=req.currency,
        preferred_broker=req.preferred_broker,
        user_id=str(user["id"]),
    )
    await log_audit("bracket_order", user_id=user["id"], details=result)
    return result


@router.post("/orders/signal")
async def execute_signal(req: SignalExecutionRequest, authorization: str = Header(None)):
    """Execute a trading signal (from decision agent or manual)."""
    user = await _require_trading_access(authorization)

    from agents.live_execution_agent import LiveExecutionAgent
    agent = LiveExecutionAgent()

    result = await agent.execute_signal(
        symbol=req.symbol,
        signal={
            "action": req.action,
            "confidence": req.confidence,
            "entry_price": req.entry_price,
            "stop_loss": req.stop_loss,
            "target_price": req.target_price,
            "position_size_recommendation": req.position_size_recommendation,
        },
        user_id=str(user["id"]),
        preferred_broker=req.preferred_broker,
        exchange=req.exchange,
        currency=req.currency,
    )

    if result.get("executed"):
        await save_trade(
            user_id=user["id"],
            symbol=req.symbol,
            action=req.action,
            quantity=result.get("quantity", 0),
            price=result.get("avg_fill_price", 0),
            order_type=result.get("order_type", "MKT"),
            mode="live",
            broker=result.get("broker", ""),
        )
    await log_audit("signal_execution", user_id=user["id"], details=result)
    return result


@router.delete("/orders/{order_id}")
async def cancel_order(order_id: str, authorization: str = Header(None)):
    """Cancel an active order."""
    user = await _require_trading_access(authorization)
    from core.order_management import get_oms
    oms = get_oms()
    result = await oms.cancel_order(order_id)
    await log_audit("cancel_order", user_id=user["id"],
                    details={"order_id": order_id, **result})
    return result


# ── Portfolio ──────────────────────────────────────────────────────────────

@router.get("/portfolio")
async def get_portfolio(authorization: str = Header(None)):
    """Get consolidated portfolio across all connected brokers."""
    await _require_trading_access(authorization)
    from tools.broker_manager import get_broker_manager
    manager = get_broker_manager()
    return await manager.get_consolidated_portfolio()


@router.get("/portfolio/{broker_id}")
async def get_broker_portfolio(broker_id: str, authorization: str = Header(None)):
    """Get portfolio for a specific broker."""
    await _require_trading_access(authorization)
    from tools.broker_manager import get_broker_manager
    manager = get_broker_manager()
    broker = manager.get_broker(broker_id)
    if not broker:
        raise HTTPException(status_code=404, detail=f"Broker {broker_id} not found")
    if not broker.is_connected:
        raise HTTPException(status_code=503, detail=f"Broker {broker_id} not connected")
    positions = await broker.get_positions()
    account = await broker.get_account()
    return {
        "broker": broker_id,
        "account": {
            "cash": account.cash_balance,
            "equity": account.total_equity,
            "margin_used": account.margin_used,
            "buying_power": account.buying_power,
        },
        "positions": [
            {
                "symbol": p.symbol,
                "quantity": p.quantity,
                "avg_cost": p.avg_cost,
                "market_value": p.market_value,
                "unrealized_pnl": p.unrealized_pnl,
            }
            for p in positions
        ],
    }


@router.get("/positions")
async def get_all_positions(authorization: str = Header(None)):
    """Get positions from all connected brokers."""
    await _require_trading_access(authorization)
    from tools.broker_manager import get_broker_manager
    manager = get_broker_manager()
    all_pos = await manager.get_all_positions()
    return {
        bid: [
            {
                "symbol": p.symbol,
                "quantity": p.quantity,
                "avg_cost": p.avg_cost,
                "market_value": p.market_value,
                "unrealized_pnl": p.unrealized_pnl,
            }
            for p in positions
        ]
        for bid, positions in all_pos.items()
    }


# ── Risk Management ───────────────────────────────────────────────────────

@router.get("/risk/status")
async def risk_status(authorization: str = Header(None)):
    """Get current risk engine status."""
    await _require_trading_access(authorization)
    from core.risk_engine import get_risk_engine
    return get_risk_engine().get_status()


@router.post("/risk/reset-daily")
async def reset_daily_risk(authorization: str = Header(None)):
    """Manually reset daily risk counters."""
    user = await _require_trading_access(authorization)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    from core.risk_engine import get_risk_engine
    get_risk_engine().reset_daily()
    await log_audit("risk_daily_reset", user_id=user["id"])
    return {"message": "Daily risk counters reset"}


# ── Emergency Controls ────────────────────────────────────────────────────

@router.post("/emergency/stop")
async def emergency_stop(authorization: str = Header(None)):
    """EMERGENCY: Activate kill switch — cancels ALL orders and closes ALL positions."""
    user = await _require_trading_access(authorization)

    from agents.live_execution_agent import LiveExecutionAgent
    agent = LiveExecutionAgent()
    result = await agent.emergency_stop(reason=f"Manual activation by user {user['id']}")

    await log_audit("emergency_stop", user_id=user["id"], details=result)
    return result


@router.post("/emergency/resume")
async def emergency_resume(authorization: str = Header(None)):
    """Deactivate kill switch and resume trading."""
    user = await _require_trading_access(authorization)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only — contact administrator")

    from agents.live_execution_agent import LiveExecutionAgent
    agent = LiveExecutionAgent()
    result = await agent.resume_trading()

    await log_audit("emergency_resume", user_id=user["id"], details=result)
    return result


@router.post("/emergency/cancel-all")
async def cancel_all_orders(authorization: str = Header(None)):
    """Cancel all open orders across all brokers."""
    user = await _require_trading_access(authorization)

    from core.order_management import get_oms
    oms = get_oms()
    result = await oms.cancel_all_orders()

    await log_audit("cancel_all_orders", user_id=user["id"], details=result)
    return result


@router.post("/emergency/close-all")
async def close_all_positions(authorization: str = Header(None)):
    """Close all positions across all brokers (market orders)."""
    user = await _require_trading_access(authorization)

    from core.order_management import get_oms
    oms = get_oms()
    result = await oms.close_all_positions(reason=f"Manual close by user {user['id']}")

    await log_audit("close_all_positions", user_id=user["id"], details=result)
    return result


# ── Compliance ─────────────────────────────────────────────────────────────

@router.get("/compliance/report")
async def compliance_report(hours: int = 24, authorization: str = Header(None)):
    """Get compliance trade report."""
    await _require_trading_access(authorization)
    from agents.compliance_agent import get_compliance_agent
    return get_compliance_agent().get_trade_report(hours=hours)


@router.get("/compliance/alerts")
async def compliance_alerts(hours: int = 24, authorization: str = Header(None)):
    """Get compliance alerts."""
    await _require_trading_access(authorization)
    from agents.compliance_agent import get_compliance_agent
    return {"alerts": get_compliance_agent().get_alerts(hours)}


# ── OMS Status ─────────────────────────────────────────────────────────────

@router.get("/oms/status")
async def oms_status(authorization: str = Header(None)):
    """Get Order Management System status."""
    await _require_trading_access(authorization)
    from core.order_management import get_oms
    return get_oms().get_status()


@router.get("/oms/audit-log")
async def oms_audit_log(authorization: str = Header(None)):
    """Get OMS audit trail."""
    user = await _require_trading_access(authorization)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    from core.order_management import get_oms
    return {"audit_log": get_oms().audit_log[-100:]}  # last 100 entries
