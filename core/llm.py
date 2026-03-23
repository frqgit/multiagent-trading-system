"""Centralized LLM client with retry logic, structured output, and token tracking."""

from __future__ import annotations

import contextvars
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

from openai import AsyncOpenAI

from core.config import get_settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None
_IS_SERVERLESS = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

# ── Pricing per 1M tokens (USD) — update when model pricing changes ──────
MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    "text-embedding-3-small": {"input": 0.02, "output": 0.00},
    "text-embedding-3-large": {"input": 0.13, "output": 0.00},
}


@dataclass
class TokenUsage:
    """Accumulates token counts and costs for a single request scope."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    llm_calls: int = 0
    cost_usd: float = 0.0
    breakdown: list[dict[str, Any]] = field(default_factory=list)

    def record(self, model: str, prompt_tok: int, completion_tok: int) -> None:
        self.prompt_tokens += prompt_tok
        self.completion_tokens += completion_tok
        self.total_tokens += prompt_tok + completion_tok
        self.llm_calls += 1
        pricing = MODEL_PRICING.get(model, MODEL_PRICING.get("gpt-4o-mini", {}))
        call_cost = (
            prompt_tok * pricing.get("input", 0) / 1_000_000
            + completion_tok * pricing.get("output", 0) / 1_000_000
        )
        self.cost_usd += call_cost
        self.breakdown.append({
            "model": model,
            "prompt_tokens": prompt_tok,
            "completion_tokens": completion_tok,
            "cost_usd": round(call_cost, 6),
        })

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "llm_calls": self.llm_calls,
            "cost_usd": round(self.cost_usd, 6),
            "breakdown": self.breakdown,
        }


# Context variable — allows the orchestrator to collect usage across async calls
_current_usage: contextvars.ContextVar[TokenUsage | None] = contextvars.ContextVar(
    "_current_usage", default=None
)


def start_tracking() -> TokenUsage:
    """Begin tracking token usage for the current async context."""
    usage = TokenUsage()
    _current_usage.set(usage)
    return usage


def get_current_usage() -> TokenUsage | None:
    """Return the active tracker (if any)."""
    return _current_usage.get()


def _get_client() -> AsyncOpenAI:
    global _client
    # On serverless, don't cache the client — container freeze/thaw causes
    # stale HTTP connections that raise APIConnectionError.
    if _client is None or _IS_SERVERLESS:
        settings = get_settings()
        # Shorter timeout + fewer retries on serverless to stay within
        # Vercel / Lambda function time limits (maxDuration 60s).
        timeout = 12.0 if _IS_SERVERLESS else 45.0
        retries = 1 if _IS_SERVERLESS else 3
        _client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=timeout,
            max_retries=retries,
        )
    return _client


async def llm_chat(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    json_mode: bool = False,
) -> str:
    """Send a chat completion request and return the assistant's response text."""
    settings = get_settings()
    client = _get_client()
    resolved_model = model or settings.llm_model

    kwargs: dict[str, Any] = {
        "model": resolved_model,
        "temperature": temperature if temperature is not None else settings.llm_temperature,
        "max_tokens": max_tokens or settings.llm_max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        response = await client.chat.completions.create(**kwargs)
    except Exception as exc:
        exc_type = type(exc).__name__
        logger.error("OpenAI API call failed (%s): %s [model=%s, serverless=%s]",
                      exc_type, exc, resolved_model, _IS_SERVERLESS)
        raise

    content = response.choices[0].message.content or ""

    # Track tokens
    usage = response.usage
    if usage:
        logger.debug("LLM response (%s tokens): %s…", usage.total_tokens, content[:120])
        tracker = _current_usage.get()
        if tracker is not None:
            tracker.record(
                resolved_model,
                usage.prompt_tokens or 0,
                usage.completion_tokens or 0,
            )
    return content


async def llm_json(
    system_prompt: str,
    user_prompt: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Convenience wrapper that returns parsed JSON from the LLM."""
    raw = await llm_chat(system_prompt, user_prompt, json_mode=True, **kwargs)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Failed to parse LLM JSON: %s", raw[:500])
        return {"error": "LLM returned invalid JSON", "raw": raw}
