"""Authentication utilities — JWT tokens, password hashing, user helpers."""

from __future__ import annotations

import datetime
from typing import Optional

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24 * 7  # 7 days

FREE_TIER_PROMPT_LIMIT = 3
PAID_MONTHLY_CREDIT_USD = 10.00

# Tier-based prompt limits
TIER_PROMPT_LIMITS = {
    "free": 3,
    "basic": 50,
    "pro": 500,
    "enterprise": -1,  # unlimited
}


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------
def create_access_token(user_id: str, email: str, role: str) -> str:
    settings = get_settings()
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
        "iat": datetime.datetime.utcnow(),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


# ---------------------------------------------------------------------------
# FastAPI dependency — extract current user from Authorization header
# ---------------------------------------------------------------------------
async def get_current_user(authorization: str | None = None) -> Optional[dict]:
    """Decode JWT from 'Bearer <token>' header and load the user row."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    payload = decode_access_token(token)
    if payload is None:
        return None
    # Lazy import to avoid circular deps
    from memory.db import _get_session_factory, User
    factory = _get_session_factory()
    async with factory() as session:
        result = await session.execute(select(User).where(User.id == payload["sub"]))
        user = result.scalar_one_or_none()
        if user is None:
            return None
        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "tier": user.tier,
            "is_approved": user.is_approved,
            "prompt_count": user.prompt_count,
            "total_cost_usd": float(user.total_cost_usd),
            "balance_usd": float(user.balance_usd),
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }
