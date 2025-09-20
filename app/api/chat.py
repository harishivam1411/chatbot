# api/chat.py (Enhanced Version)
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.db.database import get_db
from app.models.schemas import ChatRequest, ChatResponse
from app.models.db_models import ChatLog
from app.services.openai_client import generate_reply
from app.services.classifier import classify_message
from app.services.vector_store import add_to_index
from app.services.conversation_service import ConversationService
from app.core.config import settings
import uuid


router = APIRouter(prefix="/chat", tags=["chat"])
conversation_service = ConversationService()


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest, db: AsyncSession = Depends(get_db)):
    if not payload.message.strip():
        raise HTTPException(400, detail="message cannot be empty")

    user_message = payload.message.strip()
    
    # Check if this is a new conversation and if we should offer continuation
    is_new_conversation = payload.conversation_id is None
    should_offer_continuation = False
    context_data = None
    
    if is_new_conversation and payload.user_id:
        # Check if we should offer conversation continuation
        should_offer_continuation, context_data = await conversation_service.should_offer_continuation(
            db=db,
            user_id=payload.user_id,
            current_message=user_message,
            current_conversation_id=payload.conversation_id
        )
    
    # Classify the current message
    category = classify_message(user_message)
    
    # Generate conversation ID if not provided
    conversation_id = payload.conversation_id or str(uuid.uuid4())[:8]
    
    # Generate response based on whether we're offering continuation
    if should_offer_continuation and context_data:
        # Generate continuation offer
        reply = await conversation_service.generate_continuation_prompt(
            context=context_data,
            current_message=user_message
        )
        
        # Mark this as a special continuation offer
        category = "continuation_offer"
        
    else:
        # Check if user is responding to a continuation offer
        is_continuation_response = await _is_continuation_response(user_message)
        
        if is_continuation_response and payload.user_id:
            # User wants to continue previous conversation
            if "continue" in user_message.lower() or "previous" in user_message.lower() or "1" in user_message:
                # Get the context and build enhanced prompt
                history = await conversation_service.get_user_conversation_history(
                    db=db, 
                    user_id=payload.user_id,
                    exclude_conversation_id=conversation_id
                )
                
                if history:
                    context_data = await conversation_service.analyze_conversation_context(history)
                    
                    enhanced_system_prompt = await conversation_service.build_context_enhanced_prompt(
                        current_message=user_message,
                        context=context_data,
                        system_prompt="You are a helpful assistant for a developer. Keep answers concise and actionable. Continue from where the previous conversation left off.",
                        include_full_context=True
                    )
                    
                    reply = await generate_reply(user_message, system_prompt=enhanced_system_prompt)
                else:
                    reply = await generate_reply(
                        user_message,
                        system_prompt="You are a helpful assistant for a developer. Keep answers concise and actionable."
                    )
            else:
                # User wants fresh start or current question
                reply = await generate_reply(
                    user_message,
                    system_prompt="You are a helpful assistant for a developer. Keep answers concise and actionable."
                )
        else:
            # Regular conversation - but check if we have context to enhance the response
            system_prompt = "You are a helpful assistant for a developer. Keep answers concise and actionable."
            
            if payload.user_id and not is_new_conversation:
                # For ongoing conversations, get some context
                history = await conversation_service.get_user_conversation_history(
                    db=db,
                    user_id=payload.user_id,
                    exclude_conversation_id=conversation_id,
                    limit=5
                )
                
                if history:
                    context_data = await conversation_service.analyze_conversation_context(history)
                    system_prompt = await conversation_service.build_context_enhanced_prompt(
                        current_message=user_message,
                        context=context_data,
                        system_prompt=system_prompt,
                        include_full_context=False
                    )
            
            reply = await generate_reply(user_message, system_prompt=system_prompt)

    # Create and save the chat log
    log = ChatLog(
        conversation_id=conversation_id,
        user_id=payload.user_id,
        user_message=user_message,
        bot_response=reply,
        category=category,
    )

    db.add(log)
    await db.commit()
    await db.refresh(log)

    # Index user message in Chroma (async embedding)
    try:
        await add_to_index(
            doc_id=str(log.id), 
            text=user_message, 
            metadata={
                "category": category,
                "conversation_id": conversation_id,
                "user_id": log.user_id or "",
            }
        )
    except Exception:
        # Non-blocking: failures here should not break chat
        pass

    return ChatResponse(reply=reply, category=category, log_id=log.id)


async def _is_continuation_response(message: str) -> bool:
    """Check if the message is a response to a continuation offer"""
    
    message_lower = message.lower().strip()
    
    continuation_keywords = [
        "continue", "previous", "yes", "1", "first",
        "keep going", "where we left", "last time"
    ]
    
    fresh_start_keywords = [
        "fresh", "new", "current", "2", "second", "start over"
    ]
    
    # Simple heuristic: if message is short and contains continuation keywords
    if len(message_lower.split()) <= 10:
        return (
            any(keyword in message_lower for keyword in continuation_keywords) or
            any(keyword in message_lower for keyword in fresh_start_keywords)
        )
    
    return False


# Additional endpoint to get conversation context (useful for debugging)
@router.get("/context/{user_id}")
async def get_user_context(user_id: str, db: AsyncSession = Depends(get_db)):
    """Get conversation context for a user (debug endpoint)"""
    
    should_offer, context_data = await conversation_service.should_offer_continuation(
        db=db,
        user_id=user_id,
        current_message="test message"
    )
    
    return {
        "should_offer_continuation": should_offer,
        "context": context_data
    }