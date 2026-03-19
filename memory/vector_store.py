"""Simple in-process vector store using sentence embeddings for semantic memory.

Uses numpy cosine similarity for retrieval. For production, swap with
pgvector, Qdrant, or ChromaDB.
"""

from __future__ import annotations

import json
import logging
import hashlib
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from openai import AsyncOpenAI

from core.config import get_settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=get_settings().openai_api_key)
    return _client


@dataclass
class VectorEntry:
    id: str
    text: str
    embedding: np.ndarray
    metadata: dict[str, Any] = field(default_factory=dict)


class VectorStore:
    """Lightweight in-memory vector store with OpenAI embeddings."""

    def __init__(self, model: str = "text-embedding-3-small") -> None:
        self.model = model
        self._entries: list[VectorEntry] = []

    async def _embed(self, text: str) -> np.ndarray:
        client = _get_client()
        resp = await client.embeddings.create(input=[text], model=self.model)
        return np.array(resp.data[0].embedding, dtype=np.float32)

    async def add(self, text: str, metadata: dict[str, Any] | None = None) -> str:
        """Add a text + metadata entry and return its ID."""
        entry_id = hashlib.sha256(text.encode()).hexdigest()[:16]
        # Skip duplicates
        if any(e.id == entry_id for e in self._entries):
            return entry_id
        embedding = await self._embed(text)
        self._entries.append(VectorEntry(id=entry_id, text=text, embedding=embedding, metadata=metadata or {}))
        logger.debug("VectorStore: added entry %s (%d total)", entry_id, len(self._entries))
        return entry_id

    async def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Semantic search — returns top_k most similar entries."""
        if not self._entries:
            return []
        query_emb = await self._embed(query)
        scores = []
        for entry in self._entries:
            sim = float(np.dot(query_emb, entry.embedding) / (
                np.linalg.norm(query_emb) * np.linalg.norm(entry.embedding) + 1e-9
            ))
            scores.append((sim, entry))
        scores.sort(key=lambda x: x[0], reverse=True)

        return [
            {
                "id": e.id,
                "text": e.text,
                "score": round(s, 4),
                "metadata": e.metadata,
            }
            for s, e in scores[:top_k]
        ]

    async def store_analysis(self, result: dict[str, Any]) -> str:
        """Convenience: store an analysis result for future retrieval."""
        symbol = result.get("symbol", "")
        decision = result.get("decision", {})
        text = (
            f"{symbol}: {decision.get('action', 'HOLD')} "
            f"(confidence {decision.get('confidence', 0)}) — "
            f"{decision.get('reasoning', '')}"
        )
        return await self.add(text, metadata={"symbol": symbol, "result": result})

    def count(self) -> int:
        return len(self._entries)

    def clear(self) -> None:
        self._entries.clear()


# Module-level singleton
vector_store = VectorStore()
