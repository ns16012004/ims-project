"""PostgreSQL async connection pool using SQLAlchemy + asyncpg."""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from loguru import logger
from ..core.config import settings
from ..models.orm import Base

engine = None
AsyncSessionLocal = None


async def init_postgres():
    global engine, AsyncSessionLocal
    logger.info("Connecting to PostgreSQL...")
    engine = create_async_engine(
        settings.POSTGRES_DSN,
        pool_size=20,
        max_overflow=30,
        pool_pre_ping=True,
        echo=settings.DEBUG,
    )
    AsyncSessionLocal = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ PostgreSQL connected and schema initialized.")


async def close_postgres():
    global engine
    if engine:
        await engine.dispose()
        logger.info("PostgreSQL connection closed.")


async def get_db():
    """Dependency injection for FastAPI routes."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
