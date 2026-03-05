from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..agent.executor import PoetAgent
from ..database import get_db
from ..dependencies.auth import verify_user
from ..models import User
from ..services.llm import chat_completion_stream
from ..services.memory import (
    get_or_create_device,
    update_device_status,
    update_user_activity,
)

router = APIRouter()


class ChatRequest(BaseModel):
    device_id: str
    user_id: str
    message: str
    context: Optional[dict] = None
    stream: bool = False  # 是否启用流式输出


class PoemInfo(BaseModel):
    id: int
    title: str
    author: str
    content: str


class ChatResponse(BaseModel):
    reply: str
    poem: Optional[PoemInfo] = None


@router.post("/chat")
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    # 验证用户是否存在（中间件已验证，这里作为双重验证）
    user = await verify_user(request.user_id, request.device_id, db)

    # 更新设备状态（设备可以自动创建）
    await get_or_create_device(db, request.device_id)

    # 更新用户活动状态
    await update_device_status(db, request.device_id, "online")
    await update_user_activity(db, request.user_id)

    agent = PoetAgent(db=db, user_id=request.user_id, device_id=request.device_id)
    await agent.initialize()

    if request.context:
        if agent.context:
            agent.context.set_scene_context(request.context)

    # 根据 stream 参数选择输出方式
    if request.stream:
        # 流式输出
        return StreamingResponse(
            _stream_chat(agent, request.message),
            media_type="text/event-stream",
        )
    else:
        # 非流式输出
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


async def _stream_chat(agent: PoetAgent, message: str):
    """流式输出聊天响应"""
    import json

    # 保存用户消息
    await agent.context.save_user_message(message)

    # 构建消息
    messages = agent.context.build_messages("")

    # 获取工具配置
    from ..services.config import get_config
    from ..agent.tools import ToolRegistry

    tools = None
    if get_config("feature.tool_call_enabled", True):
        tools = agent.get_tools()

    model_config = agent.get_model_config()

    # 用于收集完整响应
    full_content = ""
    poem_data = None

    # 流式调用
    async for chunk in chat_completion_stream(
        messages=messages,
        tools=tools,
        temperature=model_config.get("temperature", 0.7),
        max_tokens=model_config.get("max_tokens", 500),
    ):
        # 处理内容增量
        if chunk.choices and chunk.choices[0].delta:
            delta = chunk.choices[0].delta

            # 发送内容
            if delta.content:
                full_content += delta.content
                yield f"data: {json.dumps({'type': 'content', 'data': delta.content}, ensure_ascii=False)}\n\n"

            # 处理工具调用（在流式输出的最后一个 chunk）
            if delta.tool_calls:
                # 流式输出时工具调用处理较复杂，这里简化处理
                # 实际应用中可能需要缓存工具调用并在流结束后执行
                pass

        # 处理使用统计（最后一个 chunk）
        if chunk.usage:
            yield f"data: {json.dumps({'type': 'usage', 'data': {'total_tokens': chunk.usage.total_tokens}}, ensure_ascii=False)}\n\n"

    # 保存助手回复
    if full_content:
        agent.context.add_assistant_message(content=full_content)
        await agent.context.save_assistant_message(content=full_content)

    # 发送结束标记
    yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
