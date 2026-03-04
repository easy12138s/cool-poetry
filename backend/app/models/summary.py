from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ConversationSummary(Base):
    __tablename__ = "conversation_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(36))
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    start_message_id: Mapped[Optional[str]] = mapped_column(String(36))
    end_message_id: Mapped[Optional[str]] = mapped_column(String(36))
    start_created_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    end_created_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    token_saved: Mapped[int] = mapped_column(Integer, default=0)
    key_entities: Mapped[Optional[dict]] = mapped_column(JSON)
    sentiment: Mapped[Optional[str]] = mapped_column(String(20))
    topics: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
