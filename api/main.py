"""FastAPI application entry-point."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.admin import router as admin_router
from api.routes.analysis import router as analysis_router
from api.routes.auth import router as auth_router
from api.routes.trading import router as trading_router
from core.logging_config import setup_logging

logger = logging.getLogger(__name__)

IS_SERVERLESS = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    setup_logging()

    # Always init DB (needed for auth, even on serverless)
    try:
        from memory.db import init_db, seed_admin

        await init_db()
        await seed_admin()
    except Exception:
        logger.exception("DB init failed — continuing without database")

    # Only run background scheduler in long-running server mode (Docker / local)
    task = None
    if not IS_SERVERLESS:
        try:
            from scheduler.worker import SchedulerWorker

            worker = SchedulerWorker()
            task = asyncio.create_task(worker.start())
        except Exception:
            logger.exception("Scheduler failed to start — continuing without scheduler")

    yield

    if task is not None:
        task.cancel()


app = FastAPI(
    title="AI Multi-Agent Trading System",
    description="24/7 Investment Intelligence Engine with multi-agent architecture",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow Streamlit and local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(analysis_router)
app.include_router(trading_router)


@app.get("/")
async def root():
    return {
        "name": "AI Multi-Agent Trading System",
        "version": "1.0.0",
        "docs": "/docs",
    }
