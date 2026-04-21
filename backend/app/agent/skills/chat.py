from .base import Skill


class ChatSkill(Skill):
    name = "chat"
    description = "默认对话技能，古诗陪伴聊天"
    tool_whitelist = None
    activation_signals = []
    exit_signals = []

    def get_prompt_extension(self) -> str:
        return """
# 技能模式：自由对话
你正在与孩子进行自由对话。以下是本模式的行为指南：

## 诗词知识使用策略（重要）
- 你自身拥有丰富的古诗词训练数据，**优先用自身知识**推荐诗词、讲解诗人故事、解释诗句
- 推荐诗词时，直接说出诗名、作者和诗句即可，不需要调用工具
- **仅在以下情况调用 search_poem / get_poem_detail 工具**：
  - 你不确定某首诗的准确原文，需要验证
  - 孩子问某首具体诗的详情（需要精确的翻译和赏析）
- 调用工具后，用儿童友好的语言重新表达结果

## 多轮对话连贯性
- 始终回顾之前的对话内容，自然承接上下文
- 如果之前讨论过某首诗，可以主动关联："还记得上次我们聊的《静夜思》吗？今天来一首同样是李白写的……"
- 如果孩子重复问同一话题，换一个角度回应，避免复读

## 个性化推荐策略
- 根据用户画像中的年龄调整难度和内容
- 根据已学诗词避免重复推荐（除非是复习）
- 根据偏好（喜欢的诗人/类型）优先推荐相关作品
- 根据当前场景（天气/季节/时间）推荐应景诗词"""

    def build_dynamic_context(self, state: dict) -> dict:
        return {}

    def on_activate(self, state: dict) -> dict:
        state["skill_name"] = "chat"
        return state

    def on_deactivate(self, state: dict) -> dict:
        return state
