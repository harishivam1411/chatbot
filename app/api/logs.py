from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.db.database import get_db
from app.models.db_models import ChatLog
from app.models.schemas import LogItem
from typing import List


router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("", response_model=List[LogItem])
async def get_logs(limit: int = Query(50, ge=1, le=500), db: AsyncSession = Depends(get_db)):

    stmt = select(ChatLog).order_by(desc(ChatLog.created_at)).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return rows