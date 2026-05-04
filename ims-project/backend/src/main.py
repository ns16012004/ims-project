"""
Incident Management System - Main Application Entry Point
"""
import asyncio
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from loguru import logger

from .api.signals import router as signals_router
from .api.workitems import router as workitems_router
from .api.health import router as health_router
from .api.ws import router as ws_router
from .core.config import settings
from .core.queue import signal_queue
from .db.postgres import init_postgres, close_postgres
from .db.mongo import init_mongo, close_mongo
from .db.redis import init_redis, close_redis
from .services.processor import SignalProcessor
from .core.metrics import metrics_reporter


limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - startup and shutdown."""
    logger.info("🚀 Starting Incident Management System...")

    # Initialize databases
    await init_postgres()
    await init_mongo()
    await init_redis()

    # Start background workers
    processor = SignalProcessor(signal_queue)
    processor_task = asyncio.create_task(processor.run())
    metrics_task = asyncio.create_task(metrics_reporter())

    logger.info("✅ IMS is fully operational.")
    yield

    # Graceful shutdown
    logger.info("🛑 Shutting down IMS...")
    processor_task.cancel()
    metrics_task.cancel()
    await close_postgres()
    await close_mongo()
    await close_redis()
    logger.info("👋 IMS shutdown complete.")


app = FastAPI(
    title="Incident Management System",
    description="Mission-Critical IMS for distributed stack monitoring",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(signals_router, prefix="/api/v1", tags=["signals"])
app.include_router(workitems_router, prefix="/api/v1", tags=["workitems"])
app.include_router(health_router, prefix="", tags=["health"])
app.include_router(ws_router, prefix="/ws", tags=["websocket"])


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )
