"""Health check endpoint."""
from fastapi import APIRouter
from ..core.queue import signal_queue
from ..db.postgres import engine
from ..db.redis import get_redis
from ..db.mongo import get_db as get_mongo_db

router = APIRouter()


@router.get("/health")
async def health():
    """
    Health check endpoint.
    Verifies connectivity to all backing services.
    """
    checks = {}

    # PostgreSQL
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {str(e)}"

    # Redis
    try:
        redis = get_redis()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {str(e)}"

    # MongoDB
    try:
        db = get_mongo_db()
        await db.command("ping")
        checks["mongodb"] = "ok"
    except Exception as e:
        checks["mongodb"] = f"error: {str(e)}"

    # Queue
    queue_stats = signal_queue.get_stats()
    checks["queue"] = queue_stats

    overall = "healthy" if all(
        v == "ok" for k, v in checks.items() if k != "queue"
    ) else "degraded"

    return {
        "status": overall,
        "checks": checks,
        "version": "1.0.0",
    }
