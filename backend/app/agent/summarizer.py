import json
import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.summary import ConversationSummary
from ..services.llm import chat_completion
from .tools import ToolRegistry
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class SummarizerAgent(BaseAgent):
    def __init__(self, db: AsyncSession, user_id: str):
        super().__init__("summarizer", db)
        self.user_id = user_id

    async def run(self, messages: list[dict]) -> dict:
        try:
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

            result = {
                "summary": "",
                "key_entities": None,
                "sentiment": None,
                "profile_updates": None,
                "sentiment_detail": None,
            }

            if content:
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict):
                        result["summary"] = parsed.get("summary", "")
                        result["key_entities"] = {
                            "key_poems": parsed.get("key_poems", []),
                            "key_poets": parsed.get("key_poets", []),
                            "user_interests": parsed.get("user_interests", []),
                            "unfinished_activities": parsed.get("unfinished_activities", []),
                        }
                        result["sentiment"] = parsed.get("sentiment")
                        result["profile_updates"] = parsed.get("profile_updates")
                        result["sentiment_detail"] = parsed.get("sentiment_detail")
                    else:
                        result["summary"] = content
                except json.JSONDecodeError:
                    result["summary"] = content

            profile_updates = result.get("profile_updates")
            if profile_updates and isinstance(profile_updates, dict):
                update_args = {}
                for field in ["nickname", "age", "favorite_poets", "add_preferences"]:
                    value = profile_updates.get(field)
                    if value:
                        update_args[field] = value
                mastery_updates = profile_updates.get("mastery_updates", [])
                if mastery_updates:
                    for mu in mastery_updates:
                        if isinstance(mu, dict) and mu.get("poem_id") and mu.get("poem_title"):
                            try:
                                lp_tool = ToolRegistry.get("record_learning_progress")
                                if lp_tool:
                                    await lp_tool.execute(
                                        db=self.db,
                                        user_id=self.user_id,
                                        poem_id=mu["poem_id"],
                                        poem_title=mu["poem_title"],
                                        mastery_level=mu.get("mastery_level", 1),
                                    )
                            except Exception as e:
                                logger.warning(f"Failed to record learning progress from summary: {e}")
                if update_args:
                    try:
                        up_tool = ToolRegistry.get("update_user_profile")
                        if up_tool:
                            await up_tool.execute(db=self.db, user_id=self.user_id, **update_args)
                            logger.info(f"Profile auto-updated from summary: {list(update_args.keys())}")
                    except Exception as e:
                        logger.warning(f"Failed to update profile from summary: {e}")

            if tool_calls:
                for tc in tool_calls:
                    tool_result = await self._execute_tool(tc["name"], tc["arguments"])
                    if tc["name"] == "update_user_profile":
                        logger.info(f"User profile updated via summarizer: {tool_result}")

            return result
        except Exception as e:
            logger.exception(f"SummarizerAgent.run failed: {e}")
            return {"summary": "", "key_entities": None, "sentiment": None}

    async def summarize_and_save(self, messages: list[dict]) -> Optional[ConversationSummary]:
        if not messages:
            logger.warning("No messages to summarize")
            return None

        try:
            result = await self.run(messages)

            if not result.get("summary"):
                logger.warning(f"Empty summary generated for user {self.user_id}")

            first_msg = messages[0] if messages else {}
            last_msg = messages[-1] if messages else {}

            start_time = first_msg.get("created_at") if isinstance(first_msg, dict) else datetime.now()
            end_time = last_msg.get("created_at") if isinstance(last_msg, dict) else datetime.now()

            if not start_time:
                start_time = datetime.now()
            if not end_time:
                end_time = datetime.now()

            summary = ConversationSummary(
                user_id=self.user_id,
                summary_text=result.get("summary", ""),
                message_count=len(messages),
                key_entities=result.get("key_entities"),
                sentiment=result.get("sentiment"),
                topics={
                    "sentiment_detail": result.get("sentiment_detail"),
                    "profile_updates": result.get("profile_updates"),
                },
                start_created_at=start_time,
                end_created_at=end_time,
            )

            self.db.add(summary)
            await self.db.commit()

            logger.info(f"Created summary for user {self.user_id}: {len(messages)} messages, summary length: {len(result.get('summary', ''))}")
            return summary

        except Exception as e:
            logger.exception(f"Failed to create summary for user {self.user_id}: {e}")
            try:
                await self.db.rollback()
            except:
                pass
            return None

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
