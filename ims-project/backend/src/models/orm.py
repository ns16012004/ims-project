"""SQLAlchemy ORM models for PostgreSQL (Source of Truth)."""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, DateTime, Float, Integer,
    ForeignKey, Enum as SAEnum, Text, JSON
)
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.dialects.postgresql import UUID


class Base(DeclarativeBase):
    pass


class WorkItem(Base):
    __tablename__ = "work_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    component_id = Column(String(100), nullable=False, index=True)
    component_type = Column(String(50), nullable=False)
    priority = Column(String(5), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    status = Column(
        String(20),
        nullable=False,
        default="OPEN",
        index=True
    )
    signal_count = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to RCA
    rca = relationship("RCA", back_populates="work_item", uselist=False)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "component_id": self.component_id,
            "component_type": self.component_type,
            "priority": self.priority,
            "title": self.title,
            "status": self.status,
            "signal_count": self.signal_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "rca": self.rca.to_dict() if self.rca else None,
            "mttr_minutes": self.rca.mttr_minutes if self.rca else None,
        }


class RCA(Base):
    __tablename__ = "rcas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    work_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("work_items.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    incident_start = Column(DateTime, nullable=False)
    incident_end = Column(DateTime, nullable=False)
    root_cause_category = Column(String(50), nullable=False)
    root_cause_description = Column(Text, nullable=False)
    fix_applied = Column(Text, nullable=False)
    prevention_steps = Column(Text, nullable=False)
    mttr_minutes = Column(Float, nullable=True)
    submitted_at = Column(DateTime, default=datetime.utcnow)

    work_item = relationship("WorkItem", back_populates="rca")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "work_item_id": str(self.work_item_id),
            "incident_start": self.incident_start.isoformat() if self.incident_start else None,
            "incident_end": self.incident_end.isoformat() if self.incident_end else None,
            "root_cause_category": self.root_cause_category,
            "root_cause_description": self.root_cause_description,
            "fix_applied": self.fix_applied,
            "prevention_steps": self.prevention_steps,
            "mttr_minutes": self.mttr_minutes,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
        }
