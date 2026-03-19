"""24/7 background scheduler that periodically analyzes watchlist stocks."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from agents.orchestrator import OrchestratorAgent
from core.config import get_settings
from memory.db import save_analysis
from memory.vector_store import vector_store

logger = logging.getLogger(__name__)


class SchedulerWorker:
    """Periodically runs the analysis pipeline for all watchlist symbols."""

    def __init__(self) -> None:
        self.orchestrator = OrchestratorAgent()
        self._running = False

    async def run_cycle(self) -> list[dict]:
        """Execute one full analysis cycle for all watchlist symbols."""
        settings = get_settings()
        symbols = settings.watchlist
        logger.info("[Scheduler] Starting cycle for %d symbols: %s", len(symbols), symbols)

        results = await self.orchestrator.analyze_multiple(symbols)

        # Persist each result
        for result in results:
            try:
                record_id = await save_analysis(result)
                await vector_store.store_analysis(result)
                symbol = result.get("symbol", "?")
                action = result.get("decision", {}).get("action", "?")
                logger.info("[Scheduler] Saved %s → %s (id=%s)", symbol, action, record_id)
            except Exception as exc:
                logger.error("[Scheduler] Failed to persist result: %s", exc)

        logger.info("[Scheduler] Cycle complete. Analyzed %d symbols.", len(results))
        return results

    async def start(self) -> None:
        """Start the infinite scheduler loop."""
        settings = get_settings()
        interval = settings.scheduler_interval * 60  # convert to seconds
        self._running = True

        logger.info("[Scheduler] Starting 24/7 loop (interval=%d min)", settings.scheduler_interval)

        while self._running:
            try:
                await self.run_cycle()
            except Exception as exc:
                logger.error("[Scheduler] Cycle failed: %s", exc)

            logger.info("[Scheduler] Next cycle in %d minutes…", settings.scheduler_interval)
            await asyncio.sleep(interval)

    def stop(self) -> None:
        logger.info("[Scheduler] Stopping…")
        self._running = False


async def run_scheduler() -> None:
    """Entry point for running the scheduler standalone."""
    from core.logging_config import setup_logging
    from memory.db import init_db

    setup_logging()
    await init_db()

    worker = SchedulerWorker()
    try:
        await worker.start()
    except KeyboardInterrupt:
        worker.stop()


if __name__ == "__main__":
    asyncio.run(run_scheduler())
