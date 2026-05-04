"""MongoDB connection - Data Lake for raw signal storage."""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from loguru import logger
from ..core.config import settings

_client: AsyncIOMotorClient = None
_db: AsyncIOMotorDatabase = None


async def init_mongo():
    global _client, _db
    logger.info("Connecting to MongoDB...")
    _client = AsyncIOMotorClient(settings.MONGO_URI)
    _db = _client[settings.MONGO_DB]
    # Create indexes for efficient querying
    await _db.signals.create_index("component_id")
    await _db.signals.create_index("work_item_id")
    await _db.signals.create_index("timestamp")
    await _db.signals.create_index([("component_id", 1), ("timestamp", -1)])
    logger.info("✅ MongoDB connected and indexes created.")


async def close_mongo():
    global _client
    if _client:
        _client.close()
        logger.info("MongoDB connection closed.")


def get_db() -> AsyncIOMotorDatabase:
    return _db


def get_signals_collection():
    return _db.signals
