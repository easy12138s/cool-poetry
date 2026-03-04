import json
import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.summary import ConversationSummary
from ..services.llm import chat_completion
from .base import ToolRegistry
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class SummarizerAgent(BaseAgent):
    def __init__(self, db: AsyncSession, user_id: str):
        super().__init__("summarizer", db)
        self.user_id = user_id

    async def run(self, messages: list[dict]) -> dict:
        model_config = self.get_model_config()
        system_prompt = self.get_system_prompt()

        prompt_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请分析以下对话历史：\n\n{self._format_messages(messages)}"},
        ]

        tools = self.get_tools()
        response = await chat_completion(prompt_messages, tools=tools if tools else None, **model_config)

        content = response["content"]
        tool_calls = response["tool_calls"]

        result = {"summary": content, "key_entities": None, "sentiment": None}

        if tool_calls:
            for tc in tool_calls:
                tool_result = await self._execute_tool(tc["name"], tc["arguments"])
                if tc["name"] == "analyze_conversation":
                    try:
                        result["key_entities"] = json.loads(tool_result) if isinstance(tool_result, str) else tool_result
                    except:
                        pass

        return result

    async def summarize_and_save(self, messages: list[dict]) -> Optional[ConversationSummary]:
        if not messages:
            return None

        result = await self.run(messages)

        first_msg = messages[0] if messages else {}
        last_msg = messages[-1] if messages else {}

        summary = ConversationSummary(
            user_id=self.user_id,
            summary_text=result.get("summary", ""),
            message_count=len(messages),
            key_entities=result.get("key_entities"),
            sentiment=result.get("sentiment"),
            start_created_at=datetime.now(),
            end_created_at=datetime.now(),
        )
        self.db.add(summary)
        await self.db.commit()

        logger.info(f"Created summary for user {self.user_id}: {len(messages)} messages")
        return summary

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

    def _format_messages(self, messages: list[dict]) -> str:
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if content:
                lines.append(f"[{role}]: {content}")
        return "\n".join(lines)
