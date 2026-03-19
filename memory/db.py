"""Database models and async session management using SQLAlchemy + asyncpg."""

from __future__ import annotations

import datetime
import uuid
from typing import AsyncGenerator

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, Numeric, String, Text, JSON
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from core.config import get_settings


class Base(DeclarativeBase):
    pass


class User(Base):
    """Application user with tier-based access control."""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="user")       # user | admin
    tier = Column(String(20), nullable=False, default="free")       # free | paid
    is_approved = Column(Boolean, nullable=False, default=False)
    prompt_count = Column(Integer, nullable=False, default=0)
    total_cost_usd = Column(Numeric(12, 6), nullable=False, default=0)
    balance_usd = Column(Numeric(12, 6), nullable=False, default=0)  # paid-tier credit
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class AnalysisRecord(Base):
    """Stores each analysis pipeline run."""

    __tablename__ = "analysis_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol = Column(String(10), nullable=False, index=True)
    action = Column(String(10), nullable=False)  # BUY / SELL / HOLD
    confidence = Column(Float, nullable=False)
    reasoning = Column(Text, nullable=True)
    market_data = Column(JSON, nullable=True)
    sentiment_data = Column(JSON, nullable=True)
    risk_data = Column(JSON, nullable=True)
    full_result = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)


class WatchlistItem(Base):
    """User watchlist persistence."""

    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(10), nullable=False, unique=True)
    added_at = Column(DateTime, default=datetime.datetime.utcnow)


# ---------------------------------------------------------------------------
# Engine & session factory (lazy init)
# ---------------------------------------------------------------------------
_engine = None
_session_factory = None


def _get_engine():
    global _engine
    if _engine is None:
        import os
        settings = get_settings()
        engine_kwargs: dict = {"echo": False}
        if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
            # Serverless: use NullPool (no persistent connections)
            from sqlalchemy.pool import NullPool
            engine_kwargs["poolclass"] = NullPool
        else:
            engine_kwargs["pool_size"] = 5
            engine_kwargs["max_overflow"] = 10
        _engine = create_async_engine(settings.database_url, **engine_kwargs)
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            _get_engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create all tables."""
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def seed_admin() -> None:
    """Ensure the default admin account exists."""
    from core.auth import hash_password

    ADMIN_EMAIL = "fhossain@bigpond.net.au"
    factory = _get_session_factory()
    async with factory() as session:
        from sqlalchemy import select
        result = await session.execute(select(User).where(User.email == ADMIN_EMAIL))
        if result.scalar_one_or_none() is None:
            admin = User(
                email=ADMIN_EMAIL,
                name="Admin",
                password_hash=hash_password("admin123"),
                role="admin",
                tier="paid",
                is_approved=True,
                balance_usd=10.00,
            )
            session.add(admin)
            await session.commit()


async def save_analysis(result: dict) -> str:
    """Persist an analysis result and return its ID."""
    decision = result.get("decision", {})
    record = AnalysisRecord(
        symbol=result.get("symbol", ""),
        action=decision.get("action", "HOLD"),
        confidence=decision.get("confidence", 0),
        reasoning=decision.get("reasoning", ""),
        market_data=result.get("market_data"),
        sentiment_data=result.get("sentiment"),
        risk_data=result.get("risk"),
        full_result=result,
    )
    factory = _get_session_factory()
    async with factory() as session:
        session.add(record)
        await session.commit()
        return record.id


async def get_history(symbol: str | None = None, limit: int = 20) -> list[dict]:
    """Retrieve recent analysis records."""
    from sqlalchemy import select

    factory = _get_session_factory()
    async with factory() as session:
        stmt = select(AnalysisRecord).order_by(AnalysisRecord.created_at.desc()).limit(limit)
        if symbol:
            stmt = stmt.where(AnalysisRecord.symbol == symbol.upper())
        result = await session.execute(stmt)
        rows = result.scalars().all()
        return [
            {
                "id": r.id,
                "symbol": r.symbol,
                "action": r.action,
                "confidence": r.confidence,
                "reasoning": r.reasoning,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
