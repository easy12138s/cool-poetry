import json
from collections import deque
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models.context import Message, MessageRole, SceneContext, TaskState, ToolCall
from ..models.conversation import Conversation
from ..models.user_profile import UserProfile
from .prompt import prompt_builder


class ContextManager:
    def __init__(
        self,
        session_id: str,
        user_id: str,
        device_id: str,
        db: AsyncSession,
        max_short_term: Optional[int] = None,
    ):
        self.session_id = session_id
        self.user_id = user_id
        self.device_id = device_id
        self.db = db

        max_messages = max_short_term or getattr(settings, "max_short_term_messages", 50)
        self.short_term: deque[Message] = deque(maxlen=max_messages)

        self.state = TaskState()
        self.scene_context: Optional[SceneContext] = None
        self._profile_cache: Optional[dict] = None

        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return

        await self._load_history()
        await self._load_profile()
        self._initialized = True

    async def _load_history(self, limit: int = 10) -> None:
        """加载历史会话，按时间升序排列（最旧的在最前）

        确保消息按正确的时间顺序加载，这样 LLM 才能理解对话的上下文。
        """
        # 1. 查询最近的消息（按时间降序，最新的在前）
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.user_id == self.user_id)
            .order_by(Conversation.created_at.desc())
            .limit(limit * 2)
        )
        convs_desc = result.scalars().all()

        # 2. 转换为 Message 对象并过滤无效消息
        messages_desc = []
        for conv in convs_desc:
            message = self._conversation_to_message(conv)
            if message:
                messages_desc.append(message)

        # 3. 反转列表，变成时间升序（最旧的在最前）
        messages_asc = list(reversed(messages_desc))

        # 4. 只保留最近 limit 条消息
        recent_messages = messages_asc[-limit:] if len(messages_asc) > limit else messages_asc

        # 5. 按顺序添加到 short_term
        for msg in recent_messages:
            self.short_term.append(msg)

    def _conversation_to_message(self, conv: Conversation) -> Optional[Message]:
        role_map = {
            "user": MessageRole.USER,
            "assistant": MessageRole.ASSISTANT,
            "tool": MessageRole.TOOL,
        }

        role = role_map.get(conv.role)
        if not role:
            return None

        tool_calls = None
        if conv.tool_calls:
            try:
                tc_list = json.loads(conv.tool_calls) if isinstance(conv.tool_calls, str) else conv.tool_calls
                tool_calls = [ToolCall(**tc) for tc in tc_list]
            except (json.JSONDecodeError, TypeError):
                pass

        return Message(
            role=role,
            content=conv.content,
            tool_calls=tool_calls,
            tool_call_id=conv.tool_call_id,
            created_at=conv.created_at or datetime.now(),
        )

    async def _load_profile(self) -> None:
        result = await self.db.execute(
            select(UserProfile).where(UserProfile.user_id == self.user_id)
        )
        profile = result.scalar_one_or_none()

        if profile:
            self._profile_cache = profile.to_dict()
        else:
            self._profile_cache = None

    def set_scene_context(self, context: Optional[dict]) -> None:
        if context:
            self.scene_context = SceneContext(
                weather=context.get("weather"),
                time=context.get("time"),
                season=context.get("season"),
                location=context.get("location"),
                custom=context.get("custom"),
            )
        else:
            self.scene_context = None

    def add_message(self, message: Message) -> None:
        self.short_term.append(message)

    def add_user_message(self, content: str) -> Message:
        message = Message(role=MessageRole.USER, content=content)
        self.add_message(message)
        return message

    def add_assistant_message(
        self,
        content: Optional[str] = None,
        tool_calls: Optional[list[ToolCall]] = None,
    ) -> Message:
        message = Message(
            role=MessageRole.ASSISTANT,
            content=content,
            tool_calls=tool_calls,
        )
        self.add_message(message)
        return message

    def add_tool_message(self, tool_call_id: str, content: str) -> Message:
        message = Message(
            role=MessageRole.TOOL,
            content=content,
            tool_call_id=tool_call_id,
        )
        self.add_message(message)
        return message

    async def persist_message(self, message: Message) -> Conversation:
        tool_calls_str = None
        if message.tool_calls:
            tool_calls_str = json.dumps([tc.model_dump() for tc in message.tool_calls])

        conversation = Conversation(
            id=str(uuid4()),
            user_id=self.user_id,
            device_id=self.device_id,
            role=message.role.value,
            content=message.content or "",
            tool_calls=tool_calls_str,
            tool_call_id=message.tool_call_id,
        )
        self.db.add(conversation)
        await self.db.commit()
        return conversation

    async def save_user_message(self, content: str) -> Conversation:
        message = self.add_user_message(content)
        return await self.persist_message(message)

    async def save_assistant_message(
        self,
        content: Optional[str] = None,
        tool_calls: Optional[list[ToolCall]] = None,
    ) -> Conversation:
        message = self.add_assistant_message(content, tool_calls)
        return await self.persist_message(message)

    async def save_tool_message(self, tool_call_id: str, content: str) -> Conversation:
        message = self.add_tool_message(tool_call_id, content)
        return await self.persist_message(message)

    def update_state(self, **kwargs) -> None:
        self.state.update(**kwargs)

    def set_last_poem(self, poem_id: int, title: str, author: str) -> None:
        self.state.last_poem_id = poem_id
        self.state.last_poem_title = title
        self.state.last_poem_author = author

    async def update_profile(self, **kwargs) -> None:
        result = await self.db.execute(
            select(UserProfile).where(UserProfile.user_id == self.user_id)
        )
        profile = result.scalar_one_or_none()

        if not profile:
            profile = UserProfile(user_id=self.user_id)
            self.db.add(profile)

        for key, value in kwargs.items():
            if hasattr(profile, key):
                setattr(profile, key, value)

        await self.db.commit()
        self._profile_cache = profile.to_dict()

    def get_profile(self) -> Optional[dict]:
        return self._profile_cache

    def get_history(self) -> list[dict]:
        return [msg.to_openai_format() for msg in self.short_term]

    def build_messages(self, user_message: str, system_prompt: Optional[str] = None) -> list[dict]:
        history = self.get_history()
        return prompt_builder.build_messages(
            user_message=user_message,
            conversation_history=history,
            scene_context=self.scene_context,
            user_profile=self._profile_cache,
            task_state=self.state,
            system_prompt=system_prompt,
        )

    def get_context_summary(self) -> str:
        if not self.short_term:
            return "无对话历史"

        parts = []
        if self.state.last_poem_title:
            parts.append(f"最近讨论的诗词：《{self.state.last_poem_title}》")
            if self.state.last_poem_author:
                parts[-1] += f" - {self.state.last_poem_author}"

        if self.state.finished_steps:
            parts.append(f"已完成步骤：{', '.join(self.state.finished_steps)}")

        return " | ".join(parts) if parts else "对话刚开始"

    def clear_short_term(self) -> None:
        self.short_term.clear()
        self.state = TaskState()

    async def clear_all(self) -> None:
        self.clear_short_term()
        self.scene_context = None
        await self.db.commit()


def generate_session_id() -> str:
    return str(uuid4())
