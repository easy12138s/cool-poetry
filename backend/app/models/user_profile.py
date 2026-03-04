from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    nickname: Mapped[Optional[str]] = mapped_column(String(50))
    age: Mapped[Optional[int]] = mapped_column()
    favorite_poets: Mapped[Optional[dict]] = mapped_column(JSON, default=list)
    favorite_poems: Mapped[Optional[dict]] = mapped_column(JSON, default=list)
    learning_progress: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    preferences: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "nickname": self.nickname,
            "age": self.age,
            "favorite_poets": self.favorite_poets or [],
            "favorite_poems": self.favorite_poems or [],
            "learning_progress": self.learning_progress or {},
            "preferences": self.preferences or {},
            "notes": self.notes,
        }
