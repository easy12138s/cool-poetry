from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..agent.executor import PoetAgent
from ..database import get_db
from ..services.memory import (
    get_or_create_device,
    get_or_create_user,
    update_device_status,
    update_user_activity,
)

router = APIRouter()


class ChatRequest(BaseModel):
    device_id: str
    user_id: str
    message: str
    context: Optional[dict] = None


class PoemInfo(BaseModel):
    id: int
    title: str
    author: str
    content: str


class ChatResponse(BaseModel):
    reply: str
    poem: Optional[PoemInfo] = None


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    await get_or_create_device(db, request.device_id)
    await get_or_create_user(db, request.user_id, request.device_id)

    await update_device_status(db, request.device_id, "online")
    await update_user_activity(db, request.user_id)

    agent = PoetAgent(db=db, user_id=request.user_id, device_id=request.device_id)
    await agent.initialize()

    if request.context:
        if agent.context:
            agent.context.set_scene_context(request.context)

    reply, poem_data = await agent.run(request.message)

    poem_info = None
    if poem_data:
        poem_info = PoemInfo(
            id=poem_data.get("id", 0),
            title=poem_data.get("title", ""),
            author=poem_data.get("author", ""),
            content="",
        )

    return ChatResponse(reply=reply, poem=poem_info)
