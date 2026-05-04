"""Work Item service - business logic for work item management."""
import uuid
from datetime import datetime
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from sqlalchemy.orm import selectinload

from ..models.orm import WorkItem, RCA
from ..models.schemas import RCACreate, WorkItemStatus
from ..services.state_machine import validate_transition
from ..db.redis import cache_set, cache_get, cache_invalidate_pattern


async def get_all_work_items(db: AsyncSession, status: str = None, priority: str = None) -> list:
    cache_key = f"workitems:list:{status}:{priority}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    stmt = select(WorkItem).options(selectinload(WorkItem.rca))
    if status:
        stmt = stmt.where(WorkItem.status == status)
    if priority:
        stmt = stmt.where(WorkItem.priority == priority)
    stmt = stmt.order_by(WorkItem.priority.asc(), WorkItem.created_at.desc())

    result = await db.execute(stmt)
    items = result.scalars().all()
    data = [item.to_dict() for item in items]
    await cache_set(cache_key, data, ttl=15)
    return data


async def get_work_item_by_id(db: AsyncSession, work_item_id: str) -> dict | None:
    cache_key = f"workitems:{work_item_id}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    stmt = (
        select(WorkItem)
        .options(selectinload(WorkItem.rca))
        .where(WorkItem.id == uuid.UUID(work_item_id))
    )
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    if not item:
        return None
    data = item.to_dict()
    await cache_set(cache_key, data, ttl=30)
    return data


async def update_work_item_status(
    db: AsyncSession, work_item_id: str, new_status: str
) -> dict:
    stmt = (
        select(WorkItem)
        .options(selectinload(WorkItem.rca))
        .where(WorkItem.id == uuid.UUID(work_item_id))
    )
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    if not item:
        raise ValueError(f"Work item {work_item_id} not found")

    # Validate state transition (raises ValueError if invalid)
    validate_transition(item.status, new_status, rca=item.rca)

    async with db.begin_nested():
        item.status = new_status
        item.updated_at = datetime.utcnow()

    await db.commit()
    await cache_invalidate_pattern(f"workitems:{work_item_id}")
    await cache_invalidate_pattern("workitems:list:*")
    await cache_invalidate_pattern("dashboard:*")
    return item.to_dict()


async def submit_rca(db: AsyncSession, work_item_id: str, rca_data: RCACreate) -> dict:
    """Submit RCA for a work item. Work item must be in RESOLVED state."""
    stmt = (
        select(WorkItem)
        .options(selectinload(WorkItem.rca))
        .where(WorkItem.id == uuid.UUID(work_item_id))
    )
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    if not item:
        raise ValueError(f"Work item {work_item_id} not found")

    if item.rca:
        raise ValueError("RCA already submitted for this work item.")

    # Calculate MTTR
    delta = rca_data.incident_end - rca_data.incident_start
    mttr = round(delta.total_seconds() / 60, 2)

    rca = RCA(
        id=uuid.uuid4(),
        work_item_id=uuid.UUID(work_item_id),
        incident_start=rca_data.incident_start,
        incident_end=rca_data.incident_end,
        root_cause_category=rca_data.root_cause_category,
        root_cause_description=rca_data.root_cause_description,
        fix_applied=rca_data.fix_applied,
        prevention_steps=rca_data.prevention_steps,
        mttr_minutes=mttr,
    )
    db.add(rca)
    await db.commit()
    await db.refresh(item)

    await cache_invalidate_pattern(f"workitems:{work_item_id}")
    await cache_invalidate_pattern("workitems:list:*")
    await cache_invalidate_pattern("dashboard:*")
    logger.info(f"✅ RCA submitted for {work_item_id}, MTTR={mttr} min")
    return item.to_dict()


async def get_dashboard_stats(db: AsyncSession) -> dict:
    cache_key = "dashboard:stats"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    # Count by status
    status_counts = await db.execute(
        select(WorkItem.status, func.count(WorkItem.id))
        .group_by(WorkItem.status)
    )
    status_map = dict(status_counts.all())

    # Count by priority (open only)
    priority_counts = await db.execute(
        select(WorkItem.priority, func.count(WorkItem.id))
        .where(WorkItem.status.in_(["OPEN", "INVESTIGATING"]))
        .group_by(WorkItem.priority)
    )
    priority_map = dict(priority_counts.all())

    # Avg MTTR
    avg_mttr = await db.execute(select(func.avg(RCA.mttr_minutes)))
    avg_val = avg_mttr.scalar()

    stats = {
        "total_open": status_map.get("OPEN", 0),
        "total_investigating": status_map.get("INVESTIGATING", 0),
        "total_resolved": status_map.get("RESOLVED", 0),
        "total_closed": status_map.get("CLOSED", 0),
        "p0_count": priority_map.get("P0", 0),
        "p1_count": priority_map.get("P1", 0),
        "p2_count": priority_map.get("P2", 0),
        "avg_mttr_minutes": round(avg_val, 2) if avg_val else None,
    }
    await cache_set(cache_key, stats, ttl=10)
    return stats
