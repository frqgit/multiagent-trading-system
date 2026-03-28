"""Stripe billing integration — subscription management for Basic/Pro/Enterprise tiers.

Handles:
- Checkout session creation
- Webhook processing (subscription lifecycle)
- Customer portal links
- Tier management
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_stripe = None
_stripe_available = False


def _ensure_stripe():
    global _stripe, _stripe_available
    if _stripe is not None:
        return _stripe_available
    try:
        import stripe as _mod
        _stripe = _mod
        _stripe_available = True
    except ImportError:
        _stripe_available = False
    return _stripe_available


# Tier definitions: name → { price_monthly_aud, features, stripe_price_id }
TIERS = {
    "free": {
        "name": "Free",
        "price_monthly_aud": 0,
        "prompts_per_month": 3,
        "features": ["3 AI analysis prompts", "Basic market data", "Community support"],
    },
    "basic": {
        "name": "Basic",
        "price_monthly_aud": 15,
        "prompts_per_month": 50,
        "stripe_price_id": "",  # Set after creating Stripe product
        "features": [
            "50 AI prompts/month",
            "Full market analysis",
            "News sentiment",
            "Risk assessment",
            "Email support",
        ],
    },
    "pro": {
        "name": "Pro",
        "price_monthly_aud": 49,
        "prompts_per_month": 500,
        "stripe_price_id": "",
        "features": [
            "500 AI prompts/month",
            "Advanced technical analysis",
            "Portfolio optimization",
            "Backtesting engine",
            "Volatility modeling",
            "Priority support",
        ],
    },
    "enterprise": {
        "name": "Enterprise",
        "price_monthly_aud": 149,
        "prompts_per_month": -1,  # unlimited
        "stripe_price_id": "",
        "features": [
            "Unlimited AI prompts",
            "All Pro features",
            "IBKR integration",
            "Custom strategies",
            "API access",
            "Dedicated support",
        ],
    },
}


def _get_stripe():
    """Initialize and return the Stripe module configured with the secret key."""
    if not _ensure_stripe():
        return None
    from core.config import get_settings
    settings = get_settings()
    if not settings.stripe_secret_key:
        return None
    _stripe.api_key = settings.stripe_secret_key
    return _stripe


async def create_checkout_session(
    user_id: str,
    user_email: str,
    tier: str,
    success_url: str = "http://localhost:8501?payment=success",
    cancel_url: str = "http://localhost:8501?payment=cancelled",
) -> dict[str, Any]:
    """Create a Stripe Checkout Session for a subscription."""
    stripe = _get_stripe()
    if stripe is None:
        return {"error": "Stripe is not configured. Contact admin."}

    tier_info = TIERS.get(tier)
    if not tier_info or tier == "free":
        return {"error": f"Invalid tier: {tier}"}

    try:
        # Create or retrieve Stripe customer
        customers = stripe.Customer.list(email=user_email, limit=1)
        if customers.data:
            customer = customers.data[0]
        else:
            customer = stripe.Customer.create(
                email=user_email,
                metadata={"user_id": user_id},
            )

        # Create a price dynamically if no price_id set
        price_id = tier_info.get("stripe_price_id")
        if not price_id:
            # Create product + price on the fly (first time)
            product = stripe.Product.create(
                name=f"TradingEdge {tier_info['name']}",
                description=f"TradingEdge {tier_info['name']} Plan - {tier_info['prompts_per_month']} prompts/month",
                metadata={"tier": tier},
            )
            price = stripe.Price.create(
                product=product.id,
                unit_amount=tier_info["price_monthly_aud"] * 100,  # cents
                currency="aud",
                recurring={"interval": "month"},
            )
            price_id = price.id

        session = stripe.checkout.Session.create(
            customer=customer.id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"user_id": user_id, "tier": tier},
        )

        return {
            "checkout_url": session.url,
            "session_id": session.id,
        }
    except Exception as e:
        logger.error("Stripe checkout creation failed: %s", e)
        return {"error": str(e)}


async def create_portal_session(user_email: str, return_url: str = "http://localhost:8501") -> dict[str, Any]:
    """Create a Stripe Customer Portal session for managing subscriptions."""
    stripe = _get_stripe()
    if stripe is None:
        return {"error": "Stripe is not configured."}

    try:
        customers = stripe.Customer.list(email=user_email, limit=1)
        if not customers.data:
            return {"error": "No subscription found for this email."}

        session = stripe.billing_portal.Session.create(
            customer=customers.data[0].id,
            return_url=return_url,
        )
        return {"portal_url": session.url}
    except Exception as e:
        logger.error("Stripe portal creation failed: %s", e)
        return {"error": str(e)}


async def handle_webhook(payload: bytes, sig_header: str) -> dict[str, Any]:
    """Process Stripe webhook events (subscription lifecycle)."""
    stripe = _get_stripe()
    if stripe is None:
        return {"error": "Stripe not configured"}

    from core.config import get_settings
    settings = get_settings()

    try:
        if settings.stripe_webhook_secret:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.stripe_webhook_secret
            )
        else:
            import json
            event = json.loads(payload)
    except ValueError:
        return {"error": "Invalid payload"}
    except stripe.error.SignatureVerificationError:
        return {"error": "Invalid signature"}

    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    logger.info("Stripe webhook: %s", event_type)

    if event_type == "checkout.session.completed":
        return await _handle_checkout_completed(data)
    elif event_type == "customer.subscription.updated":
        return await _handle_subscription_updated(data)
    elif event_type == "customer.subscription.deleted":
        return await _handle_subscription_deleted(data)
    elif event_type == "invoice.payment_succeeded":
        return await _handle_payment_succeeded(data)
    elif event_type == "invoice.payment_failed":
        return await _handle_payment_failed(data)

    return {"status": "ignored", "event_type": event_type}


async def _handle_checkout_completed(data: dict) -> dict:
    """Upgrade user tier after successful checkout."""
    metadata = data.get("metadata", {})
    user_id = metadata.get("user_id")
    tier = metadata.get("tier", "basic")
    customer_email = data.get("customer_email", "")

    if not user_id and customer_email:
        # Look up user by email
        from memory.db import _get_session_factory, User
        from sqlalchemy import select
        factory = _get_session_factory()
        async with factory() as session:
            result = await session.execute(select(User).where(User.email == customer_email))
            user = result.scalar_one_or_none()
            if user:
                user_id = user.id

    if user_id:
        await _update_user_tier(user_id, tier, data.get("subscription"))

    return {"status": "processed", "user_id": user_id, "tier": tier}


async def _handle_subscription_updated(data: dict) -> dict:
    customer_email = data.get("customer_email", "")
    status = data.get("status", "")

    if status in ("active", "trialing"):
        logger.info("Subscription active for %s", customer_email)
    elif status in ("past_due", "unpaid"):
        logger.warning("Subscription %s for %s", status, customer_email)

    return {"status": "processed", "subscription_status": status}


async def _handle_subscription_deleted(data: dict) -> dict:
    """Downgrade user to free tier when subscription is cancelled."""
    customer = data.get("customer")
    if customer:
        stripe = _get_stripe()
        if stripe:
            try:
                cust = stripe.Customer.retrieve(customer)
                email = cust.get("email", "")
                if email:
                    from memory.db import _get_session_factory, User
                    from sqlalchemy import select
                    factory = _get_session_factory()
                    async with factory() as session:
                        result = await session.execute(select(User).where(User.email == email))
                        user = result.scalar_one_or_none()
                        if user:
                            user.tier = "free"
                            user.balance_usd = 0
                            await session.commit()
                            logger.info("Downgraded %s to free tier", email)
            except Exception as e:
                logger.error("Error handling subscription deletion: %s", e)

    return {"status": "processed", "action": "downgraded"}


async def _handle_payment_succeeded(data: dict) -> dict:
    """Refresh user credits on successful recurring payment."""
    customer_email = data.get("customer_email", "")
    amount = data.get("amount_paid", 0) / 100  # cents to dollars

    if customer_email:
        from memory.db import _get_session_factory, User
        from sqlalchemy import select
        factory = _get_session_factory()
        async with factory() as session:
            result = await session.execute(select(User).where(User.email == customer_email))
            user = result.scalar_one_or_none()
            if user:
                tier_info = TIERS.get(user.tier, TIERS["basic"])
                user.balance_usd = float(amount)
                user.prompt_count = 0  # Reset monthly count
                await session.commit()

    return {"status": "processed", "action": "credits_refreshed"}


async def _handle_payment_failed(data: dict) -> dict:
    logger.warning("Payment failed for customer %s", data.get("customer_email", "unknown"))
    return {"status": "processed", "action": "payment_failed_logged"}


async def _update_user_tier(user_id: str, tier: str, subscription_id: str | None = None):
    """Update a user's tier and subscription info in the database."""
    from memory.db import _get_session_factory, User
    from sqlalchemy import select

    tier_info = TIERS.get(tier, TIERS["basic"])
    factory = _get_session_factory()
    async with factory() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            user.tier = tier
            user.is_approved = True
            user.balance_usd = tier_info["price_monthly_aud"]
            if subscription_id:
                user.stripe_subscription_id = subscription_id
            await session.commit()
            logger.info("Upgraded user %s to %s tier", user.email, tier)


def get_tier_info(tier: str) -> dict:
    """Get tier details."""
    return TIERS.get(tier, TIERS["free"])


def get_all_tiers() -> dict:
    """Get all available tiers."""
    return TIERS
