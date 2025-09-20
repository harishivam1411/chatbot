
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from app.models.db_models import ChatLog
from app.services.openai_client import generate_reply
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import json


class ConversationService:
    """Service to handle conversation continuity and context management"""
    
    def __init__(self):
        self.max_history_messages = 10  # Limit context size
        self.recent_conversation_threshold = timedelta(hours=24)  # Consider conversations within 24h as recent
    
    async def get_user_conversation_history(
        self, 
        db: AsyncSession, 
        user_id: str, 
        exclude_conversation_id: Optional[str] = None,
        limit: int = 20
    ) -> List[ChatLog]:
        """Get recent conversation history for a user, excluding current conversation"""
        
        stmt = select(ChatLog).where(ChatLog.user_id == user_id)
        
        if exclude_conversation_id:
            stmt = stmt.where(ChatLog.conversation_id != exclude_conversation_id)
        
        # Get conversations from last 7 days
        cutoff_date = datetime.utcnow() - timedelta(days=7)
        stmt = stmt.where(ChatLog.created_at >= cutoff_date)
        
        stmt = stmt.order_by(desc(ChatLog.created_at)).limit(limit)
        
        result = await db.execute(stmt)
        return result.scalars().all()
    
    async def analyze_conversation_context(self, history: List[ChatLog]) -> Dict:
        """Analyze conversation history to extract context and topics"""
        
        if not history:
            return {"has_context": False}
        
        # Group by conversation_id to get conversation topics
        conversations = {}
        for log in history:
            conv_id = log.conversation_id
            if conv_id not in conversations:
                conversations[conv_id] = {
                    "messages": [],
                    "categories": set(),
                    "last_activity": log.created_at,
                    "message_count": 0
                }
            
            conversations[conv_id]["messages"].append({
                "user_message": log.user_message,
                "bot_response": log.bot_response,
                "category": log.category,
                "created_at": log.created_at
            })
            conversations[conv_id]["categories"].add(log.category)
            conversations[conv_id]["message_count"] += 1
            
            # Update last activity if this message is more recent
            if log.created_at > conversations[conv_id]["last_activity"]:
                conversations[conv_id]["last_activity"] = log.created_at
        
        # Find the most recent significant conversation
        most_recent_conv = None
        most_recent_time = None
        
        for conv_id, conv_data in conversations.items():
            # Consider conversations with at least 2 messages as significant
            if conv_data["message_count"] >= 2:
                if most_recent_time is None or conv_data["last_activity"] > most_recent_time:
                    most_recent_conv = conv_data
                    most_recent_time = conv_data["last_activity"]
        
        if not most_recent_conv:
            return {"has_context": False}
        
        # Check if the conversation is recent enough to suggest continuation
        time_since_last = datetime.utcnow() - most_recent_time
        is_recent = time_since_last <= self.recent_conversation_threshold
        
        return {
            "has_context": True,
            "is_recent": is_recent,
            "last_activity": most_recent_time,
            "time_since_last": time_since_last,
            "categories": list(most_recent_conv["categories"]),
            "dominant_category": max(most_recent_conv["categories"], 
                                   key=lambda x: sum(1 for msg in most_recent_conv["messages"] 
                                                   if msg["category"] == x)),
            "message_count": most_recent_conv["message_count"],
            "recent_messages": most_recent_conv["messages"][-3:],  # Last 3 messages for context
            "conversation_summary": await self._summarize_conversation(most_recent_conv["messages"])
        }
    
    async def _summarize_conversation(self, messages: List[Dict]) -> str:
        """Create a brief summary of the conversation topic"""
        
        # Take first few and last few messages to understand the topic
        context_messages = messages[:3] + messages[-3:] if len(messages) > 6 else messages
        
        conversation_text = ""
        for msg in context_messages:
            conversation_text += f"User: {msg['user_message']}\n"
            conversation_text += f"Assistant: {msg['bot_response']}\n\n"
        
        summary_prompt = f"""
        Analyze this conversation and provide a brief 1-2 sentence summary of the main topic or area of discussion:

        {conversation_text}

        Respond with just the summary, focusing on the key topic or learning area.
        """
        
        try:
            summary = await generate_reply(summary_prompt.strip())
            return summary
        except Exception:
            return "Previous conversation topics"
    
    async def should_offer_continuation(
        self, 
        db: AsyncSession, 
        user_id: str, 
        current_message: str,
        current_conversation_id: Optional[str] = None
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Determine if we should offer conversation continuation to the user
        Returns (should_offer, context_data)
        """
        
        if not user_id:
            return False, None
        
        # Get user's conversation history
        history = await self.get_user_conversation_history(
            db, user_id, exclude_conversation_id=current_conversation_id
        )
        
        if not history:
            return False, None
        
        # Analyze the context
        context = await self.analyze_conversation_context(history)
        
        if not context["has_context"]:
            return False, None
        
        # Only offer continuation for recent conversations with meaningful content
        if context["is_recent"] and context["message_count"] >= 2:
            return True, context
        
        return False, context
    
    async def generate_continuation_prompt(self, context: Dict, current_message: str) -> str:
        """Generate a response that offers to continue the previous conversation"""
        
        dominant_category = context["dominant_category"]
        conversation_summary = context["conversation_summary"]
        time_ago = self._format_time_ago(context["time_since_last"])
        
        category_phrases = {
            "learn": "learning session",
            "question": "Q&A discussion", 
            "doubt": "troubleshooting session",
            "understanding": "explanation session",
            "other": "conversation"
        }
        
        session_type = category_phrases.get(dominant_category, "conversation")
        
        continuation_prompt = f"""
        I notice you had a {session_type} with me {time_ago} about: {conversation_summary}
        
        Would you like to continue where we left off, or shall I help you with your current question: "{current_message}"?
        
        Just let me know if you'd like to:
        1. Continue the previous topic
        2. Start fresh with your current question
        3. Or I can help with both!
        """
        
        return continuation_prompt
    
    def _format_time_ago(self, time_delta: timedelta) -> str:
        """Format timedelta into human-readable string"""
        
        hours = int(time_delta.total_seconds() // 3600)
        minutes = int((time_delta.total_seconds() % 3600) // 60)
        
        if hours > 24:
            days = hours // 24
            return f"{days} day{'s' if days > 1 else ''} ago"
        elif hours > 0:
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif minutes > 0:
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "just now"
    
    async def build_context_enhanced_prompt(
        self, 
        current_message: str, 
        context: Dict, 
        system_prompt: str,
        include_full_context: bool = False
    ) -> str:
        """Build an enhanced prompt with conversation context"""
        
        if not context or not context.get("has_context"):
            return system_prompt
        
        context_section = ""
        if include_full_context and context.get("recent_messages"):
            context_section = "\n\nPrevious conversation context:\n"
            for msg in context["recent_messages"]:
                context_section += f"User: {msg['user_message']}\n"
                context_section += f"Assistant: {msg['bot_response']}\n\n"
        else:
            context_section = f"\n\nPrevious conversation summary: {context['conversation_summary']}"
        
        enhanced_prompt = f"""
        {system_prompt}
        
        IMPORTANT: This user has previous conversation history with you.{context_section}
        
        Consider this context when responding, but focus primarily on their current message: "{current_message}"
        
        If relevant, you can reference previous discussions to provide better continuity and personalized assistance.
        """
        
        return enhanced_prompt