from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": self.arguments,
            },
        }


class Message(BaseModel):
    role: MessageRole
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)

    def to_openai_format(self) -> dict:
        if self.role == MessageRole.TOOL:
            return {
                "role": self.role.value,
                "tool_call_id": self.tool_call_id,
                "content": self.content,
            }
        elif self.role == MessageRole.ASSISTANT and self.tool_calls:
            return {
                "role": self.role.value,
                "content": self.content,
                "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            }
        else:
            return {
                "role": self.role.value,
                "content": self.content,
            }


class TaskState(BaseModel):
    current_step: str = ""
    plan: List[str] = Field(default_factory=list)
    finished_steps: List[str] = Field(default_factory=list)
    intermediate_data: Dict[str, Any] = Field(default_factory=dict)
    last_tool_used: Optional[str] = None
    last_poem_id: Optional[int] = None
    last_poem_title: Optional[str] = None
    last_poem_author: Optional[str] = None

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def add_finished_step(self, step: str) -> None:
        if step not in self.finished_steps:
            self.finished_steps.append(step)

    def set_intermediate(self, key: str, value: Any) -> None:
        self.intermediate_data[key] = value

    def get_intermediate(self, key: str, default: Any = None) -> Any:
        return self.intermediate_data.get(key, default)


class SceneContext(BaseModel):
    weather: Optional[str] = None
    time: Optional[str] = None
    season: Optional[str] = None
    location: Optional[str] = None
    custom: Optional[Dict[str, Any]] = None

    def is_empty(self) -> bool:
        return not any([
            self.weather,
            self.time,
            self.season,
            self.location,
            self.custom,
        ])

    def to_prompt_text(self) -> str:
        parts = []
        if self.weather:
            parts.append(f"天气：{self.weather}")
        if self.time:
            parts.append(f"时间：{self.time}")
        if self.season:
            parts.append(f"季节：{self.season}")
        if self.location:
            parts.append(f"地点：{self.location}")
        if self.custom:
            for key, value in self.custom.items():
                parts.append(f"{key}：{value}")
        return "，".join(parts) if parts else ""
