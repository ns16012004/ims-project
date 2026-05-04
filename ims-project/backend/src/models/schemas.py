"""Domain models for the Incident Management System."""
from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
import uuid


# ─── Enums ────────────────────────────────────────────────────────────────────

class ComponentType(str, Enum):
    RDBMS = "RDBMS"
    API = "API"
    MCP_HOST = "MCP_HOST"
    DISTRIBUTED_CACHE = "CACHE"
    ASYNC_QUEUE = "ASYNC_QUEUE"
    NOSQL = "NOSQL"


class SignalType(str, Enum):
    ERROR = "ERROR"
    LATENCY_SPIKE = "LATENCY_SPIKE"
    TIMEOUT = "TIMEOUT"
    HEALTH_FAIL = "HEALTH_FAIL"
    CONNECTION_REFUSED = "CONNECTION_REFUSED"


class Priority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class WorkItemStatus(str, Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class RootCauseCategory(str, Enum):
    INFRASTRUCTURE = "INFRASTRUCTURE"
    APPLICATION = "APPLICATION"
    NETWORK = "NETWORK"
    DATABASE = "DATABASE"
    HUMAN_ERROR = "HUMAN_ERROR"
    THIRD_PARTY = "THIRD_PARTY"
    UNKNOWN = "UNKNOWN"


# ─── Signal (Raw Ingestion) ────────────────────────────────────────────────────

class SignalIngest(BaseModel):
    """Incoming signal payload from monitored components."""
    component_id: str = Field(..., description="e.g., CACHE_CLUSTER_01, RDBMS_PRIMARY")
    component_type: ComponentType
    signal_type: SignalType
    message: str
    metadata: Optional[dict] = Field(default_factory=dict)
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)

    @field_validator("component_id")
    @classmethod
    def validate_component_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("component_id cannot be empty")
        return v.upper().strip()


class SignalRecord(SignalIngest):
    """Signal as stored in MongoDB."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    work_item_id: Optional[str] = None
    ingested_at: datetime = Field(default_factory=datetime.utcnow)


# ─── RCA ──────────────────────────────────────────────────────────────────────

class RCACreate(BaseModel):
    """RCA submission payload."""
    incident_start: datetime
    incident_end: datetime
    root_cause_category: RootCauseCategory
    root_cause_description: str = Field(..., min_length=20)
    fix_applied: str = Field(..., min_length=10)
    prevention_steps: str = Field(..., min_length=10)

    @field_validator("incident_end")
    @classmethod
    def end_after_start(cls, v, info):
        if "incident_start" in info.data and v <= info.data["incident_start"]:
            raise ValueError("incident_end must be after incident_start")
        return v


class RCARecord(RCACreate):
    """RCA as stored in DB."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    work_item_id: str
    mttr_minutes: Optional[float] = None
    submitted_at: datetime = Field(default_factory=datetime.utcnow)

    def calculate_mttr(self) -> float:
        delta = self.incident_end - self.incident_start
        return round(delta.total_seconds() / 60, 2)


# ─── Work Item ────────────────────────────────────────────────────────────────

class WorkItemCreate(BaseModel):
    component_id: str
    component_type: ComponentType
    priority: Priority
    title: str
    signal_ids: List[str] = Field(default_factory=list)


class WorkItemUpdate(BaseModel):
    status: WorkItemStatus


class WorkItemResponse(BaseModel):
    id: str
    component_id: str
    component_type: str
    priority: str
    title: str
    status: WorkItemStatus
    signal_count: int
    created_at: datetime
    updated_at: datetime
    rca: Optional[dict] = None
    mttr_minutes: Optional[float] = None

    class Config:
        from_attributes = True


# ─── Dashboard State ──────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_open: int
    total_investigating: int
    total_resolved: int
    total_closed: int
    p0_count: int
    p1_count: int
    p2_count: int
    signals_last_hour: int
    avg_mttr_minutes: Optional[float]
