from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db import get_db
from app.schemas import ChatRequest, ChatResponse
from app.models import ChatLog
from app.services.openai_client import generate_reply
from app.services.classifier import classify_message
from app.services.vector_store import add_to_index
from app.core.config import settings
import uuid


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest, db: AsyncSession = Depends(get_db)):
    if not payload.message.strip():
        raise HTTPException(400, detail="message cannot be empty")


    category = classify_message(payload.message)
    reply = await generate_reply(
        payload.message,
        system_prompt=("You are a helpful assistant for a developer. Keep answers concise and actionable."),
    )


    log = ChatLog(
        conversation_id=payload.conversation_id or str(uuid.uuid4())[:8],
        user_id=payload.user_id,
        user_message=payload.message,
        bot_response=reply,
        category=category,
    )

    db.add(log)
    await db.commit()
    await db.refresh(log)

    # Index user message in Chroma (async embedding)
    try:
        await add_to_index(doc_id=str(log.id), text=payload.message, metadata={
            "category": category,
            "conversation_id": log.conversation_id or "",
            "user_id": log.user_id or "",
        })
    except Exception:
    # Non-blocking: failures here should not break chat
        pass


    return ChatResponse(reply=reply, category=category, log_id=log.id)