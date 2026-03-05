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

            # 尝试解析 JSON 格式的响应
            result = {"summary": "", "key_entities": None, "sentiment": None}
            
            if content:
                try:
                    # 尝试解析 JSON
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
                    else:
                        result["summary"] = content
                except json.JSONDecodeError:
                    # 不是 JSON，直接使用内容
                    result["summary"] = content

            # 处理工具调用结果（补充信息）
            if tool_calls:
                for tc in tool_calls:
                    tool_result = await self._execute_tool(tc["name"], tc["arguments"])
                    if tc["name"] == "analyze_conversation":
                        try:
                            entities = json.loads(tool_result) if isinstance(tool_result, str) else tool_result
                            if isinstance(entities, dict) and not result["key_entities"]:
                                result["key_entities"] = entities
                        except Exception as e:
                            logger.warning(f"Failed to parse analyze_conversation result: {e}")
                    elif tc["name"] == "update_user_profile":
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
            
            # 检查摘要内容是否为空
            if not result.get("summary"):
                logger.warning(f"Empty summary generated for user {self.user_id}")

            # 从消息中提取时间戳
            first_msg = messages[0] if messages else {}
            last_msg = messages[-1] if messages else {}
            
            # 尝试获取消息的实际创建时间
            start_time = first_msg.get("created_at") if isinstance(first_msg, dict) else datetime.now()
            end_time = last_msg.get("created_at") if isinstance(last_msg, dict) else datetime.now()
            
            # 如果没有时间戳，使用当前时间
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
