import asyncio
import json
import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.context import ToolCall
from ..services.config import get_config
from ..services.context import ContextManager, generate_session_id
from ..services.llm import chat_completion
from .base import ToolRegistry
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class PoetAgent(BaseAgent):
    def __init__(self, db: AsyncSession, user_id: str, device_id: str):
        super().__init__("poet", db)
        self.user_id = user_id
        self.device_id = device_id
        self.context: Optional[ContextManager] = None
        self._max_tool_calls = 3

    async def initialize(self) -> None:
        await super().initialize()
        self.context = ContextManager(
            session_id=generate_session_id(),
            user_id=self.user_id,
            device_id=self.device_id,
            db=self.db,
        )
        await self.context.initialize()

    async def run(self, user_message: str) -> tuple[str, Optional[dict]]:
        await self.context.save_user_message(user_message)

        messages = self.context.build_messages(user_message)

        tools = None
        if get_config("feature.tool_call_enabled", True):
            tools = self.get_tools()

        model_config = self.get_model_config()
        response = await chat_completion(messages, tools=tools if tools else None, **model_config)

        content = response["content"]
        tool_calls = response["tool_calls"]
        poem_data = None
        call_count = 0

        # 收集所有 tool_calls 用于最后统一保存
        all_tool_calls = []

        while tool_calls and call_count < self._max_tool_calls:
            call_count += 1

            # 添加 assistant 的 tool_calls 到消息历史（用于 LLM 上下文）
            assistant_message = {
                "role": "assistant",
                "content": content,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": tc["arguments"]
                        }
                    }
                    for tc in tool_calls
                ]
            }
            messages.append(assistant_message)

            # 收集 tool_calls 用于最后保存
            for tc in tool_calls:
                tool_call_obj = ToolCall(id=tc["id"], name=tc["name"], arguments=tc["arguments"])
                all_tool_calls.append(tool_call_obj)

                tool_result = await self._execute_tool(tc["name"], tc["arguments"])

                # 添加 tool 消息到 LLM 上下文（符合 OpenAI 格式）
                tool_message = {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": tc["name"],
                    "content": tool_result
                }
                messages.append(tool_message)

                # 保存 tool 消息到数据库
                self.context.add_tool_message(tc["id"], tool_result)
                await self.context.save_tool_message(tc["id"], tool_result)

                # 提取诗词数据
                if tc["name"] in ["search_poem", "get_poem_detail", "get_random_poem"]:
                    extracted = self._extract_poem_data(tc["name"], tc["arguments"], tool_result)
                    if extracted:
                        poem_data = extracted
                        self.context.set_last_poem(
                            extracted.get("id", 0),
                            extracted.get("title", ""),
                            extracted.get("author", ""),
                        )

            # 再次调用 LLM
            messages = self.context.build_messages("")
            response = await chat_completion(messages, tools=tools if tools else None, **model_config)
            content = response["content"]
            tool_calls = response["tool_calls"]

        # 最后统一保存一条 assistant 消息（避免重复记录）
        if all_tool_calls:
            # 有工具调用，保存包含 tool_calls 和 content 的完整消息
            self.context.add_assistant_message(content=content, tool_calls=all_tool_calls)
            await self.context.save_assistant_message(content=content, tool_calls=all_tool_calls)
        elif content:
            # 没有工具调用，只保存 content
            self.context.add_assistant_message(content=content)
            await self.context.save_assistant_message(content=content)

        if get_config("feature.summary_enabled", True):
            asyncio.create_task(self._maybe_summarize())

        return content, poem_data

    async def _execute_tool(self, tool_name: str, arguments: str) -> str:
        tool = ToolRegistry.get(tool_name)
        if not tool:
            return f"未知的工具：{tool_name}"

        try:
            args = json.loads(arguments) if isinstance(arguments, str) else arguments
            result = await tool.execute(db=self.db, **args)
            return result
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return f"工具执行错误：{str(e)}"

    def _extract_poem_data(
        self,
        tool_name: str,
        arguments: str,
        result: str,
    ) -> Optional[dict]:
        """从工具返回结果中提取诗词数据。"""
        try:
            args = json.loads(arguments) if isinstance(arguments, str) else arguments
            result_data = json.loads(result) if isinstance(result, str) else result

            # 检查工具返回是否成功
            if isinstance(result_data, dict) and not result_data.get("success", True):
                # 工具返回失败，但 LLM 会继续对话
                return None

            # 获取 data 字段（新的返回格式）
            data = result_data.get("data") if isinstance(result_data, dict) else result_data

            if tool_name == "search_poem":
                if isinstance(data, list) and data:
                    poem = data[0]
                    return {
                        "id": poem.get("id"),
                        "title": poem.get("title", ""),
                        "author": poem.get("author", ""),
                    }
            elif tool_name == "get_poem_detail":
                if isinstance(data, dict):
                    return {
                        "id": data.get("id"),
                        "title": data.get("title", ""),
                        "author": data.get("author", ""),
                    }
            elif tool_name == "get_random_poem":
                if isinstance(data, dict):
                    return {
                        "id": data.get("id"),
                        "title": data.get("title", ""),
                        "author": data.get("author", ""),
                    }
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            logger.warning(f"Extract poem data failed: {e}")

        return None

    def _is_tool_result_successful(self, result: str) -> bool:
        """检查工具返回结果是否成功。"""
        try:
            result_data = json.loads(result) if isinstance(result, str) else result
            if isinstance(result_data, dict):
                return result_data.get("success", True)
            return True
        except (json.JSONDecodeError, TypeError):
            return True  # 非 JSON 格式认为成功（兼容旧格式）

    async def _maybe_summarize(self) -> None:
        try:
            from ..database import async_session
            from .summarizer import SummarizerAgent

            async with async_session() as db:
                threshold = get_config("summary.trigger_threshold", 20)
                count = await self._count_messages_since_last_summary(db)

                if count >= threshold:
                    summarizer = SummarizerAgent(db, self.user_id)
                    await summarizer.initialize()
                    messages = self._get_messages_for_summary()
                    if messages:
                        await summarizer.summarize_and_save(messages)
        except Exception as e:
            logger.warning(f"会话压缩失败: {e}")

    async def _count_messages_since_last_summary(self, db) -> int:
        from sqlalchemy import func, select

        from ..models.summary import ConversationSummary

        result = await db.execute(
            select(ConversationSummary)
            .where(ConversationSummary.user_id == self.user_id)
            .order_by(ConversationSummary.created_at.desc())
            .limit(1)
        )
        latest_summary = result.scalar_one_or_none()

        if latest_summary:
            from ..models.conversation import Conversation

            count_result = await db.execute(
                select(func.count())
                .select_from(Conversation)
                .where(Conversation.user_id == self.user_id)
                .where(Conversation.created_at > latest_summary.end_created_at)
            )
            return count_result.scalar() or 0
        else:
            from ..models.conversation import Conversation

            count_result = await db.execute(
                select(func.count())
                .select_from(Conversation)
                .where(Conversation.user_id == self.user_id)
            )
            return count_result.scalar() or 0

    def _get_messages_for_summary(self) -> list[dict]:
        if not self.context:
            return []
        return [msg.to_openai_format() for msg in list(self.context.short_term)]


async def run_agent(
    db: AsyncSession,
    messages: list[dict],
    max_tool_calls: int = 3,
) -> tuple[str, Optional[dict]]:
    tools = ToolRegistry.get_all_tools()

    if not tools:
        response = await chat_completion(messages)
        return response["content"], None

    response = await chat_completion(messages, tools=tools)
    content = response["content"]
    tool_calls = response["tool_calls"]

    call_count = 0
    poem_data = None

    while tool_calls and call_count < max_tool_calls:
        call_count += 1

        for tc in tool_calls:
            tool_name = tc["name"]
            arguments = tc["arguments"]

            tool_result = await execute_tool_call(db, tool_name, arguments)

            messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {"name": tool_name, "arguments": arguments},
                        }
                    ],
                }
            )
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": tool_result})

            if tool_name in ["search_poem", "get_poem_detail", "get_random_poem"]:
                poem_data = {
                    "tool": tool_name,
                    "arguments": json.loads(arguments) if isinstance(arguments, str) else arguments,
                    "result": tool_result,
                }

        response = await chat_completion(messages, tools=tools)
        content = response["content"]
        tool_calls = response["tool_calls"]

    return content, poem_data


async def execute_tool_call(
    db: AsyncSession,
    tool_name: str,
    arguments: str,
) -> str:
    tool = ToolRegistry.get(tool_name)
    if not tool:
        return f"未知的工具：{tool_name}"

    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
        result = await tool.execute(db=db, **args)
        return result
    except Exception as e:
        return f"工具执行错误：{str(e)}"
