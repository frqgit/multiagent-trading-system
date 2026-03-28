"""Billing routes — Stripe subscription management."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from core.auth import get_current_user
from core.billing import (
    create_checkout_session,
    create_portal_session,
    get_all_tiers,
    get_tier_info,
    handle_webhook,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CheckoutRequest(BaseModel):
    tier: str = Field(..., pattern="^(basic|pro|enterprise)$")
    success_url: str = Field("http://localhost:8501?payment=success")
    cancel_url: str = Field("http://localhost:8501?payment=cancelled")


class PortalRequest(BaseModel):
    return_url: str = Field("http://localhost:8501")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/tiers")
async def list_tiers():
    """List all available subscription tiers with pricing and features."""
    return {"tiers": get_all_tiers()}


@router.get("/tier/{tier_name}")
async def get_tier(tier_name: str):
    """Get details for a specific tier."""
    info = get_tier_info(tier_name)
    if not info:
        raise HTTPException(status_code=404, detail=f"Tier '{tier_name}' not found")
    return {"tier": info}


@router.post("/checkout")
async def checkout(req: CheckoutRequest, authorization: str = Header(None)):
    """Create a Stripe Checkout Session for upgrading the subscription."""
    user = await get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    result = await create_checkout_session(
        user_id=user["id"],
        user_email=user["email"],
        tier=req.tier,
        success_url=req.success_url,
        cancel_url=req.cancel_url,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/portal")
async def portal(req: PortalRequest, authorization: str = Header(None)):
    """Create a Stripe Customer Portal session for managing the subscription."""
    user = await get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    result = await create_portal_session(
        user_email=user["email"],
        return_url=req.return_url,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events (subscription lifecycle)."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    result = await handle_webhook(payload, sig_header)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result
