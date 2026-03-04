from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, Integer, String, Text, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class SystemConfig(Base):
    __tablename__ = "system_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    config_value: Mapped[str] = mapped_column(Text, nullable=False)
    config_type: Mapped[str] = mapped_column(
        Enum("string", "int", "float", "bool", "json", name="config_type_enum"),
        default="string",
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255))
    is_cacheable: Mapped[bool] = mapped_column(Boolean, default=True)
    cache_ttl: Mapped[int] = mapped_column(Integer, default=300)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
