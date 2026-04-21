from .base import Skill, SkillRegistry, SkillDetector
from .chat import ChatSkill
from .game import GameSkill
from .learning import LearningSkill

SkillRegistry.register(ChatSkill())
SkillRegistry.register(GameSkill())
SkillRegistry.register(LearningSkill())

__all__ = [
    "Skill",
    "SkillRegistry",
    "SkillDetector",
    "ChatSkill",
    "GameSkill",
    "LearningSkill",
]
