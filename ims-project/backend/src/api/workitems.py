"""Work Items API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.postgres import get_db
from ..models.schemas import WorkItemUpdate, RCACreate
from ..services import workitem_service

router = APIRouter()


@router.get("/workitems")
async def list_work_items(
    status: str = Query(None, description="Filter by status"),
    priority: str = Query(None, description="Filter by priority"),
    db: AsyncSession = Depends(get_db),
):
    items = await workitem_service.get_all_work_items(db, status=status, priority=priority)
    return {"work_items": items, "count": len(items)}


@router.get("/workitems/stats")
async def dashboard_stats(db: AsyncSession = Depends(get_db)):
    stats = await workitem_service.get_dashboard_stats(db)
    return stats


@router.get("/workitems/{work_item_id}")
async def get_work_item(work_item_id: str, db: AsyncSession = Depends(get_db)):
    item = await workitem_service.get_work_item_by_id(db, work_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Work item not found")
    return item


@router.patch("/workitems/{work_item_id}/status")
async def update_status(
    work_item_id: str,
    payload: WorkItemUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await workitem_service.update_work_item_status(
            db, work_item_id, payload.status.value
        )
        return item
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/workitems/{work_item_id}/rca")
async def submit_rca(
    work_item_id: str,
    rca: RCACreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await workitem_service.submit_rca(db, work_item_id, rca)
        return item
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
