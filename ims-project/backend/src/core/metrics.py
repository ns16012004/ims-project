"""Throughput metrics reporter - logs signals/sec every 5 seconds."""
import asyncio
import time
from loguru import logger
from .config import settings
from .queue import signal_queue


_last_processed = 0
_last_time = time.monotonic()


async def metrics_reporter():
    """Background task: prints throughput metrics every N seconds."""
    global _last_processed, _last_time

    while True:
        await asyncio.sleep(settings.METRICS_INTERVAL_SECS)
        now = time.monotonic()
        elapsed = now - _last_time
        current_processed = signal_queue.total_processed
        delta = current_processed - _last_processed
        throughput = delta / elapsed if elapsed > 0 else 0

        stats = signal_queue.get_stats()
        logger.info(
            f"📊 METRICS | "
            f"Throughput: {throughput:.1f} signals/sec | "
            f"Queue: {stats['queue_size']}/{stats['queue_max']} "
            f"({stats['utilization_pct']}%) | "
            f"Dropped: {stats['total_dropped']} "
            f"({stats['drop_rate_pct']}%)"
        )

        _last_processed = current_processed
        _last_time = now
