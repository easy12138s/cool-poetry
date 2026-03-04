import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.agent import Agent, AgentToolPermission, Tool
from ..services.config import get_config
from .base import ToolRegistry

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    def __init__(self, agent_code: str, db: AsyncSession):
        self.agent_code = agent_code
        self.db = db
        self._config: Optional[dict] = None
        self._allowed_tools: Optional[list[str]] = None
        self._system_prompt: Optional[str] = None

    async def initialize(self) -> None:
        self._config = await self._load_config()
        self._allowed_tools = await self._load_allowed_tools()
        self._system_prompt = self._config.get("system_prompt", "") if self._config else ""

    async def _load_config(self) -> dict:
        result = await self.db.execute(
            select(Agent).where(Agent.agent_code == self.agent_code, Agent.is_active == True)
        )
        agent = result.scalar_one_or_none()
        if not agent:
            raise ValueError(f"Agent not found: {self.agent_code}")
        return {
            "name": agent.agent_name,
            "system_prompt": agent.system_prompt,
            "config": agent.config or {},
        }

    async def _load_allowed_tools(self) -> list[str]:
        result = await self.db.execute(
            select(Tool.tool_code)
            .join(AgentToolPermission, AgentToolPermission.tool_id == Tool.id)
            .join(Agent, Agent.id == AgentToolPermission.agent_id)
            .where(Agent.agent_code == self.agent_code)
            .where(AgentToolPermission.is_allowed == True)
            .where(Tool.is_active == True)
        )
        return [row[0] for row in result.all()]

    def get_tools(self) -> list[dict]:
        if not self._allowed_tools:
            return []
        return ToolRegistry.get_tools_by_codes(self._allowed_tools)

    def get_model_config(self) -> dict:
        prefix = f"model.{self.agent_code}" if self.agent_code != "poet" else "model"
        return {
            "temperature": get_config(f"{prefix}.temperature", 0.7),
            "max_tokens": get_config(f"{prefix}.max_tokens", 500),
            "timeout": get_config(f"{prefix}.timeout", 30),
        }

    def get_system_prompt(self) -> str:
        return self._system_prompt or ""

    @abstractmethod
    async def run(self, *args, **kwargs) -> Any:
        pass
