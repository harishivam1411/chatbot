from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.database import get_db
from app.models.db_models import ChatLog
from app.models.schemas import AnalysisSummary


router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("", response_model=AnalysisSummary)
async def analysis(db: AsyncSession = Depends(get_db)):

    stmt = select(ChatLog.category, func.count(ChatLog.id)).group_by(ChatLog.category)
    rows = (await db.execute(stmt)).all()
    counts = {cat or "other": int(cnt) for cat, cnt in rows}
    most_used = max(counts, key=counts.get) if counts else None
    return AnalysisSummary(counts=counts, most_used=most_used)