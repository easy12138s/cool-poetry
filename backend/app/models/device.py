from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String(100))
    device_type: Mapped[str] = mapped_column(
        Enum("raspberry_pi", "mini_program", "web", name="device_type_enum"),
        default="raspberry_pi",
    )
    status: Mapped[str] = mapped_column(
        Enum("online", "offline", "sleeping", name="device_status_enum"),
        default="offline",
    )
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    config: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    users: Mapped[list["User"]] = relationship(back_populates="device")
