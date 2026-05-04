"""
Signal Processor - Background async worker.

Reads signals from the in-memory queue, applies debounce logic,
persists to MongoDB (raw), and creates/updates Work Items in PostgreSQL.
"""
import asyncio
import time
from collections import defaultdict
from datetime import datetime
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, before_log
import logging

from ..core.queue import BoundedSignalQueue
from ..core.config import settings
from ..models.schemas import SignalRecord
from ..db.mongo import get_signals_collection
from ..db.postgres import AsyncSessionLocal
from ..db.redis import cache_set, cache_delete, cache_invalidate_pattern
from ..models.orm import WorkItem
from .alerting import AlertStrategyFactory
from sqlalchemy import select, update, func
import uuid


class DebounceWindow:
    """
    Tracks signals per component within a time window.
    If threshold is reached, a single Work Item is created.
    """

    def __init__(self, window_secs: int, threshold: int):
        self.window_secs = window_secs
        self.threshold = threshold
        self._buckets: dict[str, dict] = defaultdict(lambda: {
            "count": 0,
            "first_seen": None,
            "work_item_id": None,
            "signal_ids": [],
        })

    def record(self, component_id: str, signal_id: str) -> dict:
        """
        Record a signal for a component. Returns action dict:
        - action: "create_work_item" | "link_to_existing" | "accumulate"
        """
        now = time.monotonic()
        bucket = self._buckets[component_id]

        # Reset if window has expired
        if bucket["first_seen"] and (now - bucket["first_seen"]) > self.window_secs:
            self._reset_bucket(component_id)

        if bucket["first_seen"] is None:
            bucket["first_seen"] = now

        bucket["count"] += 1
        bucket["signal_ids"].append(signal_id)

        if bucket["count"] == self.threshold and bucket["work_item_id"] is None:
            return {"action": "create_work_item", "signal_ids": bucket["signal_ids"].copy()}
        elif bucket["work_item_id"]:
            return {"action": "link_to_existing", "work_item_id": bucket["work_item_id"]}
        else:
            return {"action": "accumulate"}

    def set_work_item_id(self, component_id: str, work_item_id: str):
        self._buckets[component_id]["work_item_id"] = work_item_id

    def _reset_bucket(self, component_id: str):
        self._buckets[component_id] = {
            "count": 0,
            "first_seen": None,
            "work_item_id": None,
            "signal_ids": [],
        }


class SignalProcessor:
    """
    Async worker that drains the signal queue and handles:
    1. Persisting raw signals to MongoDB
    2. Debouncing signals per component
    3. Creating Work Items in PostgreSQL
    4. Firing alerts
    5. Invalidating Redis cache
    """

    def __init__(self, queue: BoundedSignalQueue):
        self.queue = queue
        self.debounce = DebounceWindow(
            window_secs=settings.DEBOUNCE_WINDOW_SECS,
            threshold=settings.DEBOUNCE_THRESHOLD,
        )

    async def run(self):
        """Main processing loop."""
        logger.info("🔄 Signal processor started.")
        while True:
            try:
                signal = await self.queue.get()
                await self._process(signal)
                self.queue.task_done()
            except asyncio.CancelledError:
                logger.info("Signal processor cancelled.")
                break
            except Exception as e:
                logger.error(f"Processor error: {e}", exc_info=True)

    async def _process(self, signal: dict):
        signal_id = signal.get("id", str(uuid.uuid4()))
        component_id = signal["component_id"]

        # 1. Persist raw signal to MongoDB (with retry)
        await self._persist_signal_to_mongo(signal)

        # 2. Debounce logic
        action = self.debounce.record(component_id, signal_id)

        if action["action"] == "create_work_item":
            work_item_id = await self._create_work_item(signal, action["signal_ids"])
            if work_item_id:
                self.debounce.set_work_item_id(component_id, work_item_id)
                # Update all buffered signals in Mongo with the work_item_id
                await self._link_signals_to_work_item(action["signal_ids"], work_item_id)
                await cache_invalidate_pattern("dashboard:*")
                await cache_invalidate_pattern("workitems:*")

        elif action["action"] == "link_to_existing":
            work_item_id = action["work_item_id"]
            await self._link_signal_to_work_item(signal_id, work_item_id)
            await self._increment_work_item_signal_count(work_item_id)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=0.5, max=5),
        reraise=True,
    )
    async def _persist_signal_to_mongo(self, signal: dict):
        """Persist raw signal to MongoDB with retry."""
        col = get_signals_collection()
        await col.insert_one(signal)

    async def _create_work_item(self, signal: dict, signal_ids: list) -> str | None:
        """Create a new Work Item in PostgreSQL (transactional)."""
        try:
            alert = AlertStrategyFactory.fire_alert(
                component_id=signal["component_id"],
                component_type=signal["component_type"],
                signal_type=signal["signal_type"],
                message=signal["message"],
            )
            priority = alert["priority"]

            async with AsyncSessionLocal() as session:
                async with session.begin():
                    work_item = WorkItem(
                        id=uuid.uuid4(),
                        component_id=signal["component_id"],
                        component_type=signal["component_type"],
                        priority=priority,
                        title=f"[{priority}] {signal['component_type']} failure on {signal['component_id']}",
                        status="OPEN",
                        signal_count=len(signal_ids),
                    )
                    session.add(work_item)
                    await session.flush()
                    work_item_id = str(work_item.id)

            logger.info(f"✅ Created Work Item {work_item_id} for {signal['component_id']}")
            return work_item_id
        except Exception as e:
            logger.error(f"Failed to create work item: {e}", exc_info=True)
            return None

    async def _link_signals_to_work_item(self, signal_ids: list, work_item_id: str):
        col = get_signals_collection()
        await col.update_many(
            {"id": {"$in": signal_ids}},
            {"$set": {"work_item_id": work_item_id}},
        )

    async def _link_signal_to_work_item(self, signal_id: str, work_item_id: str):
        col = get_signals_collection()
        await col.update_one(
            {"id": signal_id},
            {"$set": {"work_item_id": work_item_id}},
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=0.5, max=5))
    async def _increment_work_item_signal_count(self, work_item_id: str):
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await session.execute(
                    update(WorkItem)
                    .where(WorkItem.id == uuid.UUID(work_item_id))
                    .values(signal_count=WorkItem.signal_count + 1)
                )
