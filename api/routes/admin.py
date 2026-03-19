"""Admin routes — user management, approval, tier control."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func

from core.auth import (
    PAID_MONTHLY_CREDIT_USD,
    get_current_user,
    hash_password,
)
from memory.db import User, _get_session_factory

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _require_admin(authorization: str | None) -> dict:
    user = await get_current_user(authorization)
    if not user or user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class UpdateUserRequest(BaseModel):
    is_approved: bool | None = None
    tier: str | None = Field(None, pattern="^(free|paid)$")
    role: str | None = Field(None, pattern="^(user|admin)$")
    balance_usd: float | None = None


class AdminChangePasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=6, max_length=128)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/users")
async def list_users(authorization: str = Header(None)):
    await _require_admin(authorization)
    factory = _get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(User).order_by(User.created_at.desc())
        )
        users = result.scalars().all()
        return {
            "users": [
                {
                    "id": u.id,
                    "email": u.email,
                    "name": u.name,
                    "role": u.role,
                    "tier": u.tier,
                    "is_approved": u.is_approved,
                    "prompt_count": u.prompt_count,
                    "total_cost_usd": float(u.total_cost_usd),
                    "balance_usd": float(u.balance_usd),
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                }
                for u in users
            ]
        }


@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    req: UpdateUserRequest,
    authorization: str = Header(None),
):
    await _require_admin(authorization)
    factory = _get_session_factory()
    async with factory() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if req.is_approved is not None:
            user.is_approved = req.is_approved
        if req.tier is not None:
            user.tier = req.tier
            if req.tier == "paid" and float(user.balance_usd) <= 0:
                user.balance_usd = PAID_MONTHLY_CREDIT_USD
        if req.role is not None:
            user.role = req.role
        if req.balance_usd is not None:
            user.balance_usd = req.balance_usd

        await session.commit()
        await session.refresh(user)
        return {"message": "User updated", "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "tier": user.tier,
            "is_approved": user.is_approved,
            "balance_usd": float(user.balance_usd),
        }}


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, authorization: str = Header(None)):
    admin = await _require_admin(authorization)
    if admin["id"] == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    factory = _get_session_factory()
    async with factory() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        await session.delete(user)
        await session.commit()
        return {"message": f"User {user.email} deleted"}


@router.get("/stats")
async def admin_stats(authorization: str = Header(None)):
    await _require_admin(authorization)
    factory = _get_session_factory()
    async with factory() as session:
        total = await session.execute(select(func.count(User.id)))
        free_count = await session.execute(
            select(func.count(User.id)).where(User.tier == "free")
        )
        paid_count = await session.execute(
            select(func.count(User.id)).where(User.tier == "paid")
        )
        pending = await session.execute(
            select(func.count(User.id)).where(User.is_approved == False)
        )
        total_prompts = await session.execute(select(func.sum(User.prompt_count)))
        total_cost = await session.execute(select(func.sum(User.total_cost_usd)))
        return {
            "total_users": total.scalar() or 0,
            "free_users": free_count.scalar() or 0,
            "paid_users": paid_count.scalar() or 0,
            "pending_approval": pending.scalar() or 0,
            "total_prompts": total_prompts.scalar() or 0,
            "total_cost_usd": float(total_cost.scalar() or 0),
        }


@router.post("/change-password")
async def admin_change_password(
    req: AdminChangePasswordRequest,
    authorization: str = Header(None),
):
    admin = await _require_admin(authorization)
    factory = _get_session_factory()
    async with factory() as session:
        result = await session.execute(select(User).where(User.id == admin["id"]))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.password_hash = hash_password(req.new_password)
        await session.commit()
        return {"message": "Admin password changed successfully"}
