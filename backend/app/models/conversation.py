from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"))
    device_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("devices.id"))
    poem_id: Mapped[Optional[int]] = mapped_column(ForeignKey("poems.id"))
    role: Mapped[str] = mapped_column(
        Enum("user", "assistant", name="conversation_role_enum"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    audio_url: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    user: Mapped[Optional["User"]] = relationship(back_populates="conversations")
    poem: Mapped[Optional["Poem"]] = relationship()
