"""Authentication routes — register, login, profile."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from core.auth import (
    FREE_TIER_PROMPT_LIMIT,
    PAID_MONTHLY_CREDIT_USD,
    create_access_token,
    decode_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from memory.db import User, _get_session_factory

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=200)
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest):
    factory = _get_session_factory()
    async with factory() as session:
        existing = await session.execute(
            select(User).where(User.email == req.email.lower())
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")

        user = User(
            email=req.email.lower(),
            name=req.name.strip(),
            password_hash=hash_password(req.password),
            role="user",
            tier="free",
            is_approved=True,  # Auto-approve; admin can revoke
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        token = create_access_token(user.id, user.email, user.role)
        return TokenResponse(
            access_token=token,
            user=_user_dict(user),
        )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    factory = _get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(User).where(User.email == req.email.lower())
        )
        user = result.scalar_one_or_none()
        if not user or not verify_password(req.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        token = create_access_token(user.id, user.email, user.role)
        return TokenResponse(
            access_token=token,
            user=_user_dict(user),
        )


@router.get("/me")
async def get_profile(authorization: str = Header(None)):
    user = await get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"user": user}


@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    authorization: str = Header(None),
):
    user_data = await get_current_user(authorization)
    if not user_data:
        raise HTTPException(status_code=401, detail="Not authenticated")

    factory = _get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(User).where(User.id == user_data["id"])
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if not verify_password(req.current_password, user.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect")

        user.password_hash = hash_password(req.new_password)
        await session.commit()
        return {"message": "Password changed successfully"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user_dict(user: User) -> dict:
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
