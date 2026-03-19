"""Vercel serverless entry-point for the FastAPI backend.

Vercel's Python runtime discovers the ASGI `app` object from this module.
The lifespan events (DB init, scheduler) are handled by FastAPI's lifespan
context manager — Vercel invokes them on cold start.
"""

from api.main import app  # noqa: F401 — Vercel discovers `app`
