from abc import ABC, abstractmethod
from typing import Any, Optional


class Skill(ABC):
    name: str = ""
    description: str = ""
    tool_whitelist: Optional[list[str]] = None

    @abstractmethod
    def get_prompt_extension(self) -> str:
        """Return skill-specific prompt extension appended to base system prompt."""

    @abstractmethod
    def build_dynamic_context(self, state: dict) -> dict:
        """Build skill-specific dynamic context from current state.

        Returns:
            dict: {"user_profile_section": "...", "scene_section": "...", ...}
                  Keys correspond to template variables in prompt_builder
        """

    def on_activate(self, state: dict) -> dict:
        """Called when skill is activated. Can modify state. Returns updated state."""
        return state

    def on_deactivate(self, state: dict) -> dict:
        """Called when skill is deactivated. Can modify state. Returns updated state."""
        return state

    def get_tool_whitelist(self) -> Optional[list[str]]:
        """Return the list of tools this skill allows. None means all allowed."""
        return self.tool_whitelist


class SkillRegistry:
    _skills: dict[str, Skill] = {}

    @classmethod
    def register(cls, skill: Skill):
        cls._skills[skill.name] = skill

    @classmethod
    def get(cls, name: str) -> Optional[Skill]:
        return cls._skills.get(name)

    @classmethod
    def get_all(cls) -> dict[str, Skill]:
        return dict(cls._skills)

    @classmethod
    def clear(cls):
        cls._skills = {}

    @classmethod
    def detect_skill(cls, user_message: str, state: dict) -> str:
        """Detect which skill should be active based on user message and current state.

        Priority:
        1. If current active skill and no exit signal, keep current skill
        2. Keyword match for game intent
        3. Keyword match for learning plan intent
        4. Default to chat
        """
        current_skill = state.get("skill_name", "chat")

        active_game = state.get("game_state", {}).get("status") == "active"
        if current_skill == "game" and active_game:
            game_exit_signals = ["不玩了", "退出游戏", "结束游戏", "换个话题"]
            if not any(s in user_message for s in game_exit_signals):
                return "game"

        if current_skill == "learning":
            plan_exit_signals = ["换个话题", "不想看计划了", "继续聊天"]
            if not any(s in user_message for s in plan_exit_signals):
                return "learning"

        game_signals = ["飞花令", "诗词接龙", "填空", "游戏", "对诗", "玩"]
        if any(s in user_message for s in game_signals):
            return "game"

        learning_signals = ["学习计划", "今天学什么", "推荐一首", "每日推荐", "复习"]
        if any(s in user_message for s in learning_signals):
            return "learning"

        return "chat"
