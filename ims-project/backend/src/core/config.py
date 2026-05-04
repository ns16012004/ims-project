"""Application Configuration using Pydantic Settings."""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Incident Management System"
    DEBUG: bool = False
    SECRET_KEY: str = "super-secret-key-change-in-production"

    # PostgreSQL (Source of Truth)
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "ims_user"
    POSTGRES_PASSWORD: str = "ims_password"
    POSTGRES_DB: str = "ims_db"

    @property
    def POSTGRES_DSN(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def POSTGRES_DSN_SYNC(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # MongoDB (Data Lake - Raw Signals)
    MONGO_URI: str = "mongodb://mongo:27017"
    MONGO_DB: str = "ims_signals"

    # Redis (Cache + Hot Path)
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # Queue / Backpressure
    QUEUE_MAX_SIZE: int = 50000       # In-memory buffer cap
    DEBOUNCE_WINDOW_SECS: int = 10    # Debounce window for same component
    DEBOUNCE_THRESHOLD: int = 100     # Signals before creating work item

    # Rate Limiting
    RATE_LIMIT_SIGNALS: str = "10000/minute"
    RATE_LIMIT_API: str = "1000/minute"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Metrics
    METRICS_INTERVAL_SECS: int = 5

    # Priority mapping per component type
    COMPONENT_PRIORITY_MAP: dict = {
        "RDBMS": "P0",
        "API": "P1",
        "MCP_HOST": "P1",
        "ASYNC_QUEUE": "P1",
        "NOSQL": "P2",
        "CACHE": "P2",
    }

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
