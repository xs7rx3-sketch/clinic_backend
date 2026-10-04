import uuid
from typing import Any, Optional
from sqlalchemy import delete, select
from src.database.connection import get_db_session
from src.database.models import ChatMessage


def save_chat_message(
    patient_id: str,
    role: str,
    content: str,
    channel: str = "FLUTTER_MOBILE",
    extra_data: Optional[dict[str, Any]] = None,
) -> Optional[str]:
    """Persists a new chat message into Neon PostgreSQL chat_messages table."""
    with get_db_session() as session:
        msg = ChatMessage(
            patient_id=uuid.UUID(str(patient_id).strip()),
            role=role,
            content=content,
            channel=channel,
            extra_data=extra_data or {},
        )
        session.add(msg)
        session.flush()
        return str(msg.id)


def get_chat_history(patient_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """Retrieves chat messages for a patient in chronological order."""
    with get_db_session() as session:
        pid = uuid.UUID(str(patient_id).strip())
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.patient_id == pid)
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
        )
        messages = session.scalars(stmt).all()
        return [
            {
                "id": str(m.id),
                "patient_id": str(m.patient_id),
                "role": m.role,
                "content": m.content,
                "channel": m.channel,
                "extra_data": m.extra_data,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ]


def clear_chat_history(patient_id: str) -> int:
    """Removes stored chat messages for a specific patient."""
    with get_db_session() as session:
        pid = uuid.UUID(str(patient_id).strip())
        stmt = delete(ChatMessage).where(ChatMessage.patient_id == pid)
        res = session.execute(stmt)
        return res.rowcount
