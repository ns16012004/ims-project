"""Signal ingestion API endpoints."""
import uuid
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
from loguru import logger

from ..models.schemas import SignalIngest
from ..core.queue import signal_queue

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.post("/signals", status_code=202)
@limiter.limit("10000/minute")
async def ingest_signal(request: Request, payload: SignalIngest):
    """
    High-throughput signal ingestion endpoint.
    Immediately enqueues the signal for async processing.
    Returns 202 Accepted - does NOT wait for persistence.
    """
    signal_dict = payload.model_dump()
    signal_dict["id"] = str(uuid.uuid4())
    signal_dict["ingested_at"] = datetime.utcnow().isoformat()
    signal_dict["timestamp"] = signal_dict["timestamp"].isoformat() if signal_dict.get("timestamp") else datetime.utcnow().isoformat()

    enqueued = await signal_queue.put(signal_dict)
    if not enqueued:
        raise HTTPException(
            status_code=429,
            detail="Signal queue is full. System is under extreme load. Try again shortly."
        )

    return {
        "status": "accepted",
        "signal_id": signal_dict["id"],
        "queue_size": signal_queue.size,
    }


@router.post("/signals/batch", status_code=202)
@limiter.limit("1000/minute")
async def ingest_signals_batch(request: Request, payloads: list[SignalIngest]):
    """Batch ingestion endpoint - accepts up to 500 signals at once."""
    if len(payloads) > 500:
        raise HTTPException(status_code=400, detail="Max batch size is 500 signals.")

    accepted = 0
    dropped = 0
    for payload in payloads:
        signal_dict = payload.model_dump()
        signal_dict["id"] = str(uuid.uuid4())
        signal_dict["ingested_at"] = datetime.utcnow().isoformat()
        signal_dict["timestamp"] = signal_dict["timestamp"].isoformat() if signal_dict.get("timestamp") else datetime.utcnow().isoformat()
        if await signal_queue.put(signal_dict):
            accepted += 1
        else:
            dropped += 1

    return {
        "status": "accepted",
        "accepted": accepted,
        "dropped": dropped,
        "queue_size": signal_queue.size,
    }


@router.get("/signals/{work_item_id}")
async def get_signals_for_work_item(work_item_id: str):
    """Fetch raw signals from MongoDB for a given work item."""
    from ..db.mongo import get_signals_collection
    col = get_signals_collection()
    cursor = col.find(
        {"work_item_id": work_item_id},
        {"_id": 0}
    ).sort("timestamp", -1).limit(500)
    signals = await cursor.to_list(length=500)
    return {"signals": signals, "count": len(signals)}


@router.get("/signals/queue/stats")
async def get_queue_stats():
    """Return current queue stats for observability."""
    return signal_queue.get_stats()
