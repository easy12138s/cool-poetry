from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import run_agent
from app.database import get_db
from app.services import (
    build_messages,
    get_conversation_history,
    get_or_create_device,
    get_or_create_user,
    save_conversation,
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
    device = await get_or_create_device(db, request.device_id)
    user = await get_or_create_user(db, request.user_id, request.device_id)

    await update_device_status(db, request.device_id, "online")
    await update_user_activity(db, request.user_id)

    history = await get_conversation_history(db, request.user_id)

    messages = build_messages(request.message, history, request.context)

    reply, poem_data = await run_agent(db, messages)

    await save_conversation(
        db, request.user_id, request.device_id, "user", request.message
    )
    await save_conversation(
        db, request.user_id, request.device_id, "assistant", reply
    )

    poem_info = None
    if poem_data and "result" in poem_data:
        pass

    return ChatResponse(reply=reply, poem=poem_info)
