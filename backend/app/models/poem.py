from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Poem(Base):
    __tablename__ = "poems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    author_id: Mapped[Optional[int]] = mapped_column(ForeignKey("authors.id"))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    rhythmic: Mapped[Optional[str]] = mapped_column(String(100))
    volume: Mapped[Optional[str]] = mapped_column(String(100))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    translation: Mapped[Optional[str]] = mapped_column(Text)
    appreciation: Mapped[Optional[str]] = mapped_column(Text)
    scene_tags: Mapped[Optional[dict]] = mapped_column(JSON)
    difficulty: Mapped[int] = mapped_column(Integer, default=3)
    is_for_children: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now()
    )

    author: Mapped[Optional["Author"]] = relationship(back_populates="poems")
    paragraphs: Mapped[list["Paragraph"]] = relationship(
        back_populates="poem", order_by="Paragraph.sort_order"
    )
