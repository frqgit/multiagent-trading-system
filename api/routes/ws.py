"""WebSocket endpoints for real-time market data streaming."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts."""

    def __init__(self) -> None:
        self.active: dict[str, list[WebSocket]] = {}  # channel -> connections
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, channel: str) -> None:
        await websocket.accept()
        async with self._lock:
            self.active.setdefault(channel, []).append(websocket)
        logger.info("WS connected: channel=%s total=%d", channel, len(self.active.get(channel, [])))

    async def disconnect(self, websocket: WebSocket, channel: str) -> None:
        async with self._lock:
            conns = self.active.get(channel, [])
            if websocket in conns:
                conns.remove(websocket)

    async def broadcast(self, channel: str, data: dict[str, Any]) -> None:
        conns = self.active.get(channel, [])
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    if ws in conns:
                        conns.remove(ws)


manager = ConnectionManager()


async def _stream_market_data(websocket: WebSocket, symbols: list[str]) -> None:
    """Push market snapshots for subscribed symbols at intervals."""
    from tools.stock_api import fetch_stock_data

    while True:
        for sym in symbols:
            try:
                snap = await asyncio.to_thread(fetch_stock_data, sym)
                if snap:
                    await websocket.send_json({
                        "type": "market_data",
                        "symbol": sym,
                        "data": snap.to_dict(),
                    })
            except WebSocketDisconnect:
                return
            except Exception as exc:
                logger.debug("Market stream error for %s: %s", sym, exc)
        await asyncio.sleep(10)  # Refresh interval


async def _stream_signals(websocket: WebSocket, symbol: str) -> None:
    """Push AI signal updates for a symbol."""
    from agents.orchestrator import OrchestratorAgent

    orchestrator = OrchestratorAgent()
    while True:
        try:
            results = await orchestrator.analyze(f"Quick analysis {symbol}")
            if results:
                first = results[0] if isinstance(results, list) else results
                decision = first.get("decision", {}) if isinstance(first, dict) else {}
                await websocket.send_json({
                    "type": "ai_signal",
                    "symbol": symbol,
                    "data": {
                        "action": decision.get("action", "HOLD"),
                        "confidence": decision.get("confidence", 0),
                        "reasoning": decision.get("reasoning", ""),
                        "key_factors": decision.get("key_factors", []),
                        "suggested_entry": decision.get("suggested_entry"),
                        "target_price": decision.get("target_price"),
                        "stop_loss": decision.get("suggested_stop_loss"),
                        "time_horizon": decision.get("time_horizon"),
                    },
                })
        except WebSocketDisconnect:
            return
        except Exception as exc:
            logger.debug("Signal stream error for %s: %s", symbol, exc)
        await asyncio.sleep(60)  # AI signals refresh less frequently


@router.websocket("/ws/market")
async def ws_market(websocket: WebSocket) -> None:
    """Market data WebSocket. Send JSON: {"subscribe": ["AAPL","MSFT"]}"""
    await manager.connect(websocket, "market")
    symbols: list[str] = []
    task: asyncio.Task | None = None
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON"})
                continue

            if "subscribe" in msg:
                new_symbols = [s.upper().strip() for s in msg["subscribe"] if s.strip()][:20]
                if new_symbols:
                    symbols = new_symbols
                    if task:
                        task.cancel()
                    task = asyncio.create_task(_stream_market_data(websocket, symbols))
                    await websocket.send_json({"type": "subscribed", "symbols": symbols})

            if "unsubscribe" in msg:
                if task:
                    task.cancel()
                    task = None
                symbols = []
                await websocket.send_json({"type": "unsubscribed"})

    except WebSocketDisconnect:
        pass
    finally:
        if task:
            task.cancel()
        await manager.disconnect(websocket, "market")


@router.websocket("/ws/signals")
async def ws_signals(websocket: WebSocket) -> None:
    """AI signals WebSocket. Send JSON: {"symbol": "AAPL"}"""
    await manager.connect(websocket, "signals")
    task: asyncio.Task | None = None
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON"})
                continue

            if "symbol" in msg:
                sym = msg["symbol"].upper().strip()
                if task:
                    task.cancel()
                task = asyncio.create_task(_stream_signals(websocket, sym))
                await websocket.send_json({"type": "signal_subscribed", "symbol": sym})

    except WebSocketDisconnect:
        pass
    finally:
        if task:
            task.cancel()
        await manager.disconnect(websocket, "signals")


@router.websocket("/ws/portfolio")
async def ws_portfolio(websocket: WebSocket) -> None:
    """Portfolio updates WebSocket. Auto-pushes portfolio state."""
    await manager.connect(websocket, "portfolio")
    try:
        while True:
            try:
                from agents.execution_agent import ExecutionAgent
                agent = ExecutionAgent()
                summary = await asyncio.to_thread(
                    lambda: agent.get_portfolio_summary(symbols=[])
                )
                await websocket.send_json({
                    "type": "portfolio_update",
                    "data": summary if isinstance(summary, dict) else {},
                })
            except Exception as exc:
                logger.debug("Portfolio stream error: %s", exc)
            await asyncio.sleep(15)
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket, "portfolio")
