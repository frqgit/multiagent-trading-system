"""Database models and async session management using SQLAlchemy + asyncpg."""

from __future__ import annotations

import datetime
import uuid
from typing import AsyncGenerator

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, Numeric, String, Text, JSON, text as sa_text
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
    tier = Column(String(20), nullable=False, default="free")       # free | basic | pro | enterprise
    is_approved = Column(Boolean, nullable=False, default=False)
    prompt_count = Column(Integer, nullable=False, default=0)
    total_cost_usd = Column(Numeric(12, 6), nullable=False, default=0)
    balance_usd = Column(Numeric(12, 6), nullable=False, default=0)  # paid-tier credit
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
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


class AuditLog(Base):
    """Audit trail for all significant actions (trades, config changes, logins)."""

    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)  # trade_placed, login, config_change, etc.
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)


class UserStrategy(Base):
    """User-defined trading strategies for the strategy builder."""

    __tablename__ = "user_strategies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    strategy_type = Column(String(50), nullable=False, default="custom")  # custom, ma_crossover, rsi, etc.
    parameters = Column(JSON, nullable=False, default=dict)  # strategy params as JSON
    is_active = Column(Boolean, nullable=False, default=True)
    backtest_results = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class TradeRecord(Base):
    """Records all trades (paper and live) for audit and P&L tracking."""

    __tablename__ = "trade_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=True, index=True)
    symbol = Column(String(10), nullable=False, index=True)
    action = Column(String(10), nullable=False)  # BUY, SELL
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    order_type = Column(String(20), nullable=False, default="market")
    mode = Column(String(10), nullable=False, default="paper")  # paper | live
    broker = Column(String(20), nullable=True)  # ibkr | paper
    status = Column(String(20), nullable=False, default="filled")
    pnl = Column(Float, nullable=True)
    commission = Column(Float, nullable=True, default=0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)


# ---------------------------------------------------------------------------
# Engine & session factory (lazy init)
# ---------------------------------------------------------------------------
_engine = None
_session_factory = None


def _get_engine():
    global _engine
    if _engine is None:
        import os
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        settings = get_settings()
        db_url = settings.database_url

        # asyncpg only supports 'ssl' param, not 'sslmode', 'channel_binding', etc.
        # Strip unsupported params from the URL and keep only 'ssl' if needed.
        parsed = urlparse(db_url)
        if parsed.query:
            params = parse_qs(parsed.query)
            needs_ssl = "sslmode" in params or "ssl" in params
            # Remove all params asyncpg doesn't understand
            clean_params = {k: v[0] for k, v in params.items() if k in ("ssl",)}
            if needs_ssl and "ssl" not in clean_params:
                clean_params["ssl"] = "require"
            clean_query = urlencode(clean_params)
            db_url = urlunparse(parsed._replace(query=clean_query))

        engine_kwargs: dict = {"echo": False}
        if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
            from sqlalchemy.pool import NullPool
            engine_kwargs["poolclass"] = NullPool
        else:
            engine_kwargs["pool_size"] = 5
            engine_kwargs["max_overflow"] = 10
        _engine = create_async_engine(db_url, **engine_kwargs)
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
    """Create all tables and migrate missing columns on existing tables."""
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Migrate: add columns that may be missing on an older `users` table.
        migrations = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_subscription_id VARCHAR(255)",
        ]
        for stmt in migrations:
            await conn.execute(sa_text(stmt))


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
                password_hash=hash_password("Lorin@1999"),
                role="admin",
                tier="enterprise",
                is_approved=True,
                balance_usd=999.00,
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


async def log_audit(action: str, user_id: str | None = None,
                    details: dict | None = None, ip_address: str | None = None) -> None:
    """Write an entry to the audit log."""
    try:
        factory = _get_session_factory()
        async with factory() as session:
            entry = AuditLog(
                user_id=user_id,
                action=action,
                details=details,
                ip_address=ip_address,
            )
            session.add(entry)
            await session.commit()
    except Exception:
        logging.getLogger(__name__).error("Failed to write audit log: %s", action, exc_info=True)


async def save_trade(user_id: str | None, symbol: str, action: str,
                     quantity: float, price: float, order_type: str = "market",
                     mode: str = "paper", broker: str | None = None,
                     pnl: float | None = None, notes: str | None = None) -> str:
    """Persist a trade record and return its ID."""
    factory = _get_session_factory()
    async with factory() as session:
        record = TradeRecord(
            user_id=user_id,
            symbol=symbol,
            action=action,
            quantity=quantity,
            price=price,
            order_type=order_type,
            mode=mode,
            broker=broker,
            pnl=pnl,
            notes=notes,
        )
        session.add(record)
        await session.commit()
        return record.id


async def save_user_strategy(user_id: str, name: str, strategy_type: str,
                              parameters: dict, description: str = "") -> str:
    """Save a user-defined strategy."""
    factory = _get_session_factory()
    async with factory() as session:
        strategy = UserStrategy(
            user_id=user_id,
            name=name,
            description=description,
            strategy_type=strategy_type,
            parameters=parameters,
        )
        session.add(strategy)
        await session.commit()
        return strategy.id


async def get_user_strategies(user_id: str) -> list[dict]:
    """Get all strategies for a user."""
    from sqlalchemy import select
    factory = _get_session_factory()
    async with factory() as session:
        stmt = select(UserStrategy).where(
            UserStrategy.user_id == user_id
        ).order_by(UserStrategy.created_at.desc())
        result = await session.execute(stmt)
        rows = result.scalars().all()
        return [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "strategy_type": r.strategy_type,
                "parameters": r.parameters,
                "is_active": r.is_active,
                "backtest_results": r.backtest_results,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]


async def get_audit_logs(user_id: str | None = None, action: str | None = None,
                         limit: int = 50) -> list[dict]:
    """Retrieve audit log entries."""
    from sqlalchemy import select
    factory = _get_session_factory()
    async with factory() as session:
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        if user_id:
            stmt = stmt.where(AuditLog.user_id == user_id)
        if action:
            stmt = stmt.where(AuditLog.action == action)
        result = await session.execute(stmt)
        rows = result.scalars().all()
        return [
            {
                "id": r.id,
                "user_id": r.user_id,
                "action": r.action,
                "details": r.details,
                "ip_address": r.ip_address,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
