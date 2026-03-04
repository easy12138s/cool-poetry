from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Conversation, Device, User

MAX_HISTORY_TURNS = 10


async def get_or_create_device(
    db: AsyncSession,
    device_id: str,
    device_name: Optional[str] = None,
) -> Device:
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()

    if not device:
        device = Device(
            id=device_id,
            name=device_name or f"设备{device_id[:8]}",
            status="online",
            last_seen_at=datetime.now(),
        )
        db.add(device)
        await db.commit()
        await db.refresh(device)

    return device


async def get_or_create_user(
    db: AsyncSession,
    user_id: str,
    device_id: str,
    nickname: Optional[str] = None,
) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            id=user_id,
            device_id=device_id,
            nickname=nickname or f"小朋友{user_id[:4]}",
            last_active_at=datetime.now(),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user


async def get_conversation_history(
    db: AsyncSession,
    user_id: str,
    limit: int = MAX_HISTORY_TURNS,
) -> list[dict]:
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.created_at.desc())
        .limit(limit * 2)
    )
    conversations = list(reversed(result.scalars().all()))

    return [{"role": c.role, "content": c.content} for c in conversations]


async def save_conversation(
    db: AsyncSession,
    user_id: str,
    device_id: str,
    role: str,
    content: str,
    poem_id: Optional[int] = None,
) -> Conversation:
    conversation = Conversation(
        id=str(uuid4()),
        user_id=user_id,
        device_id=device_id,
        role=role,
        content=content,
        poem_id=poem_id,
    )
    db.add(conversation)
    await db.commit()
    return conversation


async def update_device_status(db: AsyncSession, device_id: str, status: str = "online"):
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if device:
        device.status = status
        device.last_seen_at = datetime.now()
        await db.commit()


async def update_user_activity(db: AsyncSession, user_id: str):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        user.last_active_at = datetime.now()
        await db.commit()
