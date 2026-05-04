"""
Async bounded queue for signal ingestion with backpressure support.
This decouples the HTTP ingestion layer from the persistence layer,
ensuring the system never crashes during persistence slowdowns.
"""
import asyncio
from loguru import logger
from .config import settings


class BoundedSignalQueue:
    """
    A bounded async queue that acts as an in-memory buffer between
    the ingestion API and the persistence workers.

    Backpressure Strategy:
    - Queue is capped at QUEUE_MAX_SIZE (50,000 signals)
    - When full, new signals are DROPPED with a warning logged
      (vs blocking, which would crash the ingestion API under load)
    - Metrics track drop rate so ops teams are alerted
    """

    def __init__(self, maxsize: int = None):
        self.maxsize = maxsize or settings.QUEUE_MAX_SIZE
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=self.maxsize)
        self.total_received = 0
        self.total_dropped = 0
        self.total_processed = 0

    async def put(self, signal: dict) -> bool:
        """
        Non-blocking put. Returns True if enqueued, False if dropped.
        This prevents backpressure from propagating to the HTTP layer.
        """
        self.total_received += 1
        try:
            self._queue.put_nowait(signal)
            return True
        except asyncio.QueueFull:
            self.total_dropped += 1
            logger.warning(
                f"⚠️  Queue full ({self.maxsize}). Dropping signal for "
                f"component={signal.get('component_id', 'unknown')}. "
                f"Total dropped: {self.total_dropped}"
            )
            return False

    async def get(self) -> dict:
        """Blocking get - processor waits here when queue is empty."""
        signal = await self._queue.get()
        self.total_processed += 1
        return signal

    def task_done(self):
        self._queue.task_done()

    @property
    def size(self) -> int:
        return self._queue.qsize()

    @property
    def utilization_pct(self) -> float:
        return (self._queue.qsize() / self.maxsize) * 100

    def get_stats(self) -> dict:
        return {
            "queue_size": self.size,
            "queue_max": self.maxsize,
            "utilization_pct": round(self.utilization_pct, 2),
            "total_received": self.total_received,
            "total_dropped": self.total_dropped,
            "total_processed": self.total_processed,
            "drop_rate_pct": round(
                (self.total_dropped / max(self.total_received, 1)) * 100, 2
            ),
        }


# Singleton queue instance shared across the app
signal_queue = BoundedSignalQueue()
