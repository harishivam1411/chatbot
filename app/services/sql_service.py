import asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal
from app.models.db_models import ChatSession, ChatMessage


class SqlService:

    async def check_and_add_session(self, session_id: str) -> None:

        def sync_check_and_add():
            db = AsyncSessionLocal()
            try:
                session_exist = db.query(ChatSession).filter(ChatSession.id == session_id).first()
                if not session_exist:
                    session = ChatSession(id=session_id)
                    db.add(session)
                    db.commit()
                    db.refresh(session)
                    print(f"New session created: {session_id}")
            except Exception as e:
                print(f"Error while creating session: {e}")
                db.rollback()
                raise
            finally:
                db.close()

        await asyncio.to_thread(sync_check_and_add)

    async def store_chat_message_background(self, session_id: str, sender: str, message: str, category: str):

        def sync_store_message():
            db = AsyncSessionLocal()
            try:
                chat_message = ChatMessage(
                    session_id=session_id,
                    message=message,
                    sender=sender,
                    category=category
                )
                db.add(chat_message)
                db.commit()

            except Exception as e:
                print(f"Error storing chat: {e}")
                db.rollback()
                raise
            finally:
                db.close()

        try:
            await asyncio.to_thread(sync_store_message)
        except Exception as e:
            print(f"Background task error storing chat: {e}")


    async def fetch_recent_context(self, db: AsyncSession, session_id: str):

        def sync_fetch_context():
            last_recent_context = (
                db.query(ChatMessage)
                .filter(ChatMessage.session_id == session_id, ChatMessage.sender == "assistant")
                .order_by(ChatMessage.timestamp.desc())
                .first()
            )
            return last_recent_context.message if last_recent_context else ""

        return await asyncio.to_thread(sync_fetch_context)

    async def get_session_conversation(self, session_id: str):

        def sync_get_conversation():
            db = AsyncSessionLocal()
            try:
                messages = (
                    db.query(ChatMessage)
                    .filter(ChatMessage.session_id == session_id)
                    .order_by(ChatMessage.timestamp.asc())
                    .all()
                )

                result = []
                for msg in messages:
                    result.append({
                        "id": msg.id,
                        "message": msg.message,
                        "sender": msg.sender,
                        "timestamp": msg.timestamp.isoformat()
                    })

                return result
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error fetching conversation: {str(e)}")
            finally:
                db.close()

        return await asyncio.to_thread(sync_get_conversation)
