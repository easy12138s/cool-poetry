from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, Integer, String, Text, Boolean, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ActivityState(Base):
    __tablename__ = "activity_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    activity_name: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(
        Enum("active", "paused", "completed", "cancelled", "expired", name="activity_status_enum"),
        default="active",
    )
    context: Mapped[Optional[dict]] = mapped_column(JSON)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
