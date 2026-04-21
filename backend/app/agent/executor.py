import asyncio
import json
import logging
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.context import ToolCall
from ..services.config import get_config
from ..services.context import ContextManager, generate_session_id
from ..services.llm import chat_completion
from .skills import SkillRegistry, SkillDetector
from .tools import ToolRegistry
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

    def _get_state_dict(self) -> dict:
        if not self.context:
            return {"skill_name": "chat"}
        state = self.context.state
        return {
            "skill_name": state.skill_name,
            "game_state": state.game_state,
            "daily_plan": state.daily_plan,
            "last_poem_title": state.last_poem_title,
            "last_poem_author": state.last_poem_author,
        }

    def _apply_state_dict(self, state_dict: dict) -> None:
        if not self.context:
            return
        state = self.context.state
        if "skill_name" in state_dict:
            state.skill_name = state_dict["skill_name"]
        if "game_state" in state_dict:
            state.game_state = state_dict["game_state"]
        if "daily_plan" in state_dict:
            state.daily_plan = state_dict["daily_plan"]

    async def run(self, user_message: str) -> tuple[str, Optional[dict]]:
        await self.context.save_user_message(user_message)

        asyncio.create_task(self._check_force_summary())

        state_dict = self._get_state_dict()
        new_skill_name = SkillDetector.detect(user_message, state_dict)
        current_skill_name = state_dict.get("skill_name", "chat")

        if new_skill_name != current_skill_name:
            old_skill = SkillRegistry.get(current_skill_name)
            new_skill = SkillRegistry.get(new_skill_name)
            if old_skill:
                state_dict = old_skill.on_deactivate(state_dict)
            if new_skill:
                state_dict = new_skill.on_activate(state_dict)
            self._apply_state_dict(state_dict)

        skill = SkillRegistry.get(new_skill_name)
        skill_extension = skill.get_prompt_extension() if skill else ""
        dynamic_context = skill.build_dynamic_context(state_dict) if skill else {}

        messages = self.context.build_messages(
            user_message="",
            system_prompt=self.get_system_prompt(),
            skill_extension=skill_extension,
            **dynamic_context,
        )

        tool_whitelist = skill.get_tool_whitelist() if skill else None
        tools = None
        if get_config("feature.tool_call_enabled", True):
            tools = self.get_tools(skill_whitelist=tool_whitelist)

        model_config = self.get_model_config()
        response = await chat_completion(messages, tools=tools if tools else None, **model_config)

        content = response["content"]
        tool_calls = response["tool_calls"]
        poem_data = None
        call_count = 0
        all_tool_calls = []

        while tool_calls and call_count < self._max_tool_calls:
            call_count += 1

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

            for tc in tool_calls:
                tool_call_obj = ToolCall(id=tc["id"], name=tc["name"], arguments=tc["arguments"])
                all_tool_calls.append(tool_call_obj)

                tool_result = await self._execute_tool(tc["name"], tc["arguments"])

                tool_message = {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": tc["name"],
                    "content": tool_result
                }
                messages.append(tool_message)

                self.context.add_tool_message(tc["id"], tool_result)
                await self.context.save_tool_message(tc["id"], tool_result)

                if tc["name"] in ["search_poem", "get_poem_detail"]:
                    extracted = self._extract_poem_data(tc["name"], tc["arguments"], tool_result)
                    if extracted:
                        poem_data = extracted
                        self.context.set_last_poem(
                            extracted.get("id", 0),
                            extracted.get("title", ""),
                            extracted.get("author", ""),
                        )

                if tc["name"] == "update_user_profile":
                    logger.info(f"User profile updated: user={self.user_id}")

                if tc["name"] == "record_learning_progress":
                    logger.info(f"Learning progress recorded: user={self.user_id}")

            messages = self.context.build_messages(
                "",
                system_prompt=self.get_system_prompt(),
                skill_extension=skill_extension,
                **dynamic_context,
            )
            response = await chat_completion(messages, tools=tools if tools else None, **model_config)
            content = response["content"]
            tool_calls = response["tool_calls"]

        if all_tool_calls:
            self.context.add_assistant_message(content=content, tool_calls=all_tool_calls)
            await self.context.save_assistant_message(content=content, tool_calls=all_tool_calls)
        elif content:
            self.context.add_assistant_message(content=content)
            await self.context.save_assistant_message(content=content)

        if get_config("feature.summary_enabled", True):
            asyncio.create_task(self._maybe_summarize())

        return content, poem_data

    async def _execute_tool(self, tool_name: str, arguments: str) -> str:
        tool = ToolRegistry.get(tool_name)
        if not tool:
            return json.dumps({
                "success": False,
                "message": f"未知的工具：{tool_name}"
            })

        try:
            args = json.loads(arguments) if isinstance(arguments, str) else arguments
            
            # 确保 args 是字典
            if not isinstance(args, dict):
                args = {}

            # 对于用户画像相关工具，自动传入 user_id（强制覆盖，确保使用当前登录用户）
            if tool_name in ["update_user_profile", "get_user_profile", "record_learning_progress"]:
                args["user_id"] = self.user_id

            result = await tool.execute(db=self.db, **args)
            return result
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return json.dumps({
                "success": False,
                "message": f"工具执行错误：{str(e)}"
            })

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
                
                logger.debug(f"_maybe_summarize: user={self.user_id}, messages_since_last_summary={count}, threshold={threshold}")

                if count >= threshold:
                    logger.info(f"Triggering summary for user {self.user_id}: {count} messages >= threshold {threshold}")
                    
                    summarizer = SummarizerAgent(db, self.user_id)
                    await summarizer.initialize()
                    
                    messages = self._get_messages_for_summary()
                    logger.debug(f"Got {len(messages)} messages for summary")
                    
                    if messages:
                        result = await summarizer.summarize_and_save(messages)
                        if result:
                            logger.info(f"Summary created successfully: id={result.id}, messages={result.message_count}")
                        else:
                            logger.warning(f"Summary creation returned None for user {self.user_id}")
                    else:
                        logger.warning(f"No messages to summarize for user {self.user_id}")
                else:
                    logger.debug(f"Not triggering summary: {count} < {threshold}")
        except Exception as e:
            logger.exception(f"会话压缩失败: {e}")

    async def _check_force_summary(self) -> None:
        """检查是否需要强制触发会话压缩（兜底逻辑）
        
        当消息数超过阈值2倍且没有摘要时，强制触发压缩
        """
        try:
            from ..database import async_session

            async with async_session() as db:
                threshold = get_config("summary.trigger_threshold", 20)
                
                # 获取总消息数
                total_count = await self._get_total_message_count(db)
                
                # 超过阈值2倍，检查是否有摘要
                if total_count >= threshold * 2:
                    has_summary = await self._has_any_summary(db)
                    
                    if not has_summary:
                        logger.warning(f"Force summary triggered: user={self.user_id}, total_messages={total_count}, threshold={threshold}")
                        # 强制触发压缩
                        await self._maybe_summarize()
                    else:
                        logger.debug(f"User {self.user_id} has summary, no force needed")
                else:
                    logger.debug(f"Not force summary: user={self.user_id}, count={total_count}, threshold*2={threshold*2}")
        except Exception as e:
            logger.exception(f"Force summary check failed: {e}")

    async def _get_total_message_count(self, db) -> int:
        """获取用户的总消息数"""
        from ..models.conversation import Conversation

        result = await db.execute(
            select(func.count())
            .select_from(Conversation)
            .where(Conversation.user_id == self.user_id)
        )
        return result.scalar() or 0

    async def _has_any_summary(self, db) -> bool:
        """检查用户是否有任何摘要记录"""
        from ..models.summary import ConversationSummary

        result = await db.execute(
            select(ConversationSummary)
            .where(ConversationSummary.user_id == self.user_id)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def _count_messages_since_last_summary(self, db) -> int:
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

            if tool_name in ["search_poem", "get_poem_detail"]:
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
