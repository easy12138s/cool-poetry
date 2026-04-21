from abc import ABC, abstractmethod
from typing import Any, Optional


class Skill(ABC):
    name: str = ""
    description: str = ""
    tool_whitelist: Optional[list[str]] = None
    activation_signals: list[str] = []
    exit_signals: list[str] = []

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
        """Return the list of tools this skill allows. None means all allowed.
        Override in subclasses to compute whitelist dynamically."""
        return self.tool_whitelist

    def is_sticky(self, state: dict, user_message: str) -> bool:
        """Return True if this skill should remain active given current state and message.
        Default: stay active if any exit_signal is NOT in the message."""
        if not self.exit_signals:
            return False
        return not any(s in user_message for s in self.exit_signals)

    def matches_activation(self, user_message: str) -> bool:
        """Return True if the user message matches this skill's activation signals."""
        return any(s in user_message for s in self.activation_signals)

    def __repr__(self) -> str:
        return f"Skill(name={self.name!r})"


class SkillRegistry:
    _skills: dict[str, Skill] = {}

    @classmethod
    def _ensure_init(cls):
        if "_skills" not in cls.__dict__:
            cls._skills = {}

    @classmethod
    def register(cls, skill: Skill):
        if not skill.name:
            raise ValueError("Cannot register a Skill with empty name")
        cls._ensure_init()
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


class SkillDetector:
    """Detects which skill should be active based on user message and current state.

    Queries registered skills for their activation/exit signals,
    making the detection extensible without modifying this class.
    """

    DEFAULT_SKILL = "chat"

    @classmethod
    def detect(cls, user_message: str, state: dict) -> str:
        current_skill_name = state.get("skill_name", cls.DEFAULT_SKILL)
        current_skill = SkillRegistry.get(current_skill_name)

        if current_skill and current_skill_name != cls.DEFAULT_SKILL:
            if current_skill.is_sticky(state, user_message):
                return current_skill_name

        for name, skill in SkillRegistry.get_all().items():
            if name == cls.DEFAULT_SKILL:
                continue
            if name == current_skill_name:
                continue
            if skill.matches_activation(user_message):
                return name

        return cls.DEFAULT_SKILL
