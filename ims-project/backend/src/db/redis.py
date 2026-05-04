"""Redis connection - Hot path cache for dashboard state."""
import json
import redis.asyncio as aioredis
from loguru import logger
from ..core.config import settings

_redis: aioredis.Redis = None


async def init_redis():
    global _redis
    logger.info("Connecting to Redis...")
    _redis = aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=50,
    )
    await _redis.ping()
    logger.info("✅ Redis connected.")


async def close_redis():
    global _redis
    if _redis:
        await _redis.aclose()
        logger.info("Redis connection closed.")


def get_redis() -> aioredis.Redis:
    return _redis


async def cache_set(key: str, value: dict, ttl: int = 30):
    """Set a JSON value in Redis with TTL."""
    await _redis.set(key, json.dumps(value, default=str), ex=ttl)


async def cache_get(key: str) -> dict | None:
    """Get a JSON value from Redis."""
    val = await _redis.get(key)
    if val:
        return json.loads(val)
    return None


async def cache_delete(key: str):
    await _redis.delete(key)


async def cache_invalidate_pattern(pattern: str):
    """Delete all keys matching a pattern."""
    keys = await _redis.keys(pattern)
    if keys:
        await _redis.delete(*keys)
