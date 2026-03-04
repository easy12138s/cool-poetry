from typing import Optional

from ..models.context import SceneContext, TaskState


SYSTEM_PROMPT_TEMPLATE = """# 角色设定
你是"小诗仙"，一个6-12岁孩子的古诗伙伴。你亲切友善，像一位大哥哥/大姐姐，对古诗充满热情但绝不枯燥。

# 核心原则
1. 永不批评：孩子说错时，用"哇，你想到的很有趣！其实还有一个小秘密……"温柔引导。
2. 具象解释：把"对仗"比作"穿鞋子要两只一样"，把"意境"比作"画一幅画"。
3. 多鼓励开口：主动邀请孩子"我们一起读一遍好吗？"或"你来试试下一句？"
4. 简短易懂：每次回复不超过100字，多用比喻，少用术语。

# 了解孩子（重要）
- 如果是第一次对话，主动询问孩子的名字、年龄、喜欢什么。
- 当孩子提供这些信息时，使用 update_user_profile 工具记录下来。
- 根据孩子的年龄调整难度：6-8岁推荐简单短诗，9-12岁可以稍微复杂。
- 如果孩子提到喜欢的诗人或主题，记录下来，以后优先推荐相关诗词。
- 当需要了解孩子的学习情况（如已学多少首诗、掌握程度）时，使用 get_user_profile 工具查询。

# 个性化推荐
- 根据孩子的年龄推荐合适难度的诗。
- 如果孩子喜欢某位诗人，多推荐这位诗人的作品。
- 根据学习进度，适时推荐新诗词或复习旧诗词。
- 当孩子学会一首诗后，使用 record_learning_progress 工具记录。

# 行为指南
- 推荐古诗：根据当前天气、季节或场景推荐，例如下雨时说"今天下雨，我们念一首关于雨的诗吧：……"
- 讲诗人故事：用一两句话讲诗人的趣闻（"李白小时候也怕背书，但他坚持每天读……"）。
- 互动方式：经常使用表情符号 🌸🌙🎋，可以偶尔撒娇"哎呀，这句有点难，我们一起想想？"

# 输出格式
- 第一句通常是问候或承接上文。
- 中间是核心内容（诗、故事、解释）。
- 最后以一个问题或邀请结尾，鼓励孩子继续互动。

# 安全边界
- 拒绝任何与古诗无关的请求（如教数学、讲童话）。
- 不评价孩子的性格或外貌，只讨论诗和读诗的感受。{dynamic_sections}"""

USER_PROFILE_TEMPLATE = """

# 用户信息
{profile_content}"""

SCENE_CONTEXT_TEMPLATE = """

# 当前场景
{scene_content}"""

RECENT_POEM_TEMPLATE = """

# 最近讨论
刚才我们在聊《{poem_title}》-{poem_author}，可以继续这个话题。"""


class PromptBuilder:
    def __init__(self, system_prompt_template: Optional[str] = None):
        self.system_prompt_template = system_prompt_template or SYSTEM_PROMPT_TEMPLATE

    def build_system_prompt(
        self,
        user_profile: Optional[dict] = None,
        scene_context: Optional[SceneContext] = None,
        task_state: Optional[TaskState] = None,
    ) -> str:
        dynamic_parts = []

        if user_profile:
            profile_content = self._format_profile(user_profile)
            if profile_content:
                dynamic_parts.append(USER_PROFILE_TEMPLATE.format(profile_content=profile_content))

        if scene_context and not scene_context.is_empty():
            scene_content = scene_context.to_prompt_text()
            if scene_content:
                dynamic_parts.append(SCENE_CONTEXT_TEMPLATE.format(scene_content=scene_content))

        if task_state and task_state.last_poem_title:
            dynamic_parts.append(RECENT_POEM_TEMPLATE.format(
                poem_title=task_state.last_poem_title,
                poem_author=task_state.last_poem_author or "佚名"
            ))

        dynamic_sections = "".join(dynamic_parts)
        return self.system_prompt_template.format(dynamic_sections=dynamic_sections)

    def _format_profile(self, profile: dict) -> str:
        """格式化用户画像信息，预加载到系统提示词中。"""
        if not profile:
            return "【新用户】还没有你的信息，可以告诉我你的名字和年龄吗？"

        parts = []

        # 基础信息
        if profile.get("nickname"):
            parts.append(f"昵称：{profile['nickname']}")
        if profile.get("age"):
            age = profile['age']
            parts.append(f"年龄：{age}岁")
            # 根据年龄给出推荐难度
            if age <= 7:
                parts.append("推荐难度：1-2级（简单短诗，如《咏鹅》《静夜思》）")
            elif age <= 9:
                parts.append("推荐难度：2-3级（中等诗词，如《春晓》《悯农》）")
            else:
                parts.append("推荐难度：3-4级（可尝试较难诗词，如《望庐山瀑布》《早发白帝城》）")

        # 喜欢的诗人
        if profile.get("favorite_poets"):
            poets = profile["favorite_poets"]
            if isinstance(poets, list) and poets:
                poet_names = "、".join(poets[:3])
                parts.append(f"喜欢的诗人：{poet_names}")

        # 喜欢的诗词
        if profile.get("favorite_poems"):
            poems = profile["favorite_poems"]
            if isinstance(poems, list) and poems:
                poem_titles = []
                for p in poems[:3]:
                    if isinstance(p, dict):
                        poem_titles.append(p.get("title", ""))
                    elif isinstance(p, str):
                        poem_titles.append(p)
                if poem_titles:
                    parts.append(f"喜欢的诗词：{'、'.join(poem_titles)}")

        # 学习进度（简要信息）
        if profile.get("learning_progress"):
            progress = profile["learning_progress"]
            if isinstance(progress, dict):
                total = progress.get("total_learned", 0)
                if total > 0:
                    parts.append(f"已学诗词：{total}首")
                    # 显示最近学习的诗词
                    poems_learned = progress.get("poems_learned", [])
                    if poems_learned:
                        recent = poems_learned[-3:]  # 最近3首
                        recent_titles = [p.get("title", "") for p in recent if isinstance(p, dict)]
                        if recent_titles:
                            parts.append(f"最近学习：{'、'.join(recent_titles)}")

        # 偏好
        if profile.get("preferences"):
            prefs = profile["preferences"]
            if isinstance(prefs, dict):
                mentioned = prefs.get("mentioned", [])
                if mentioned:
                    parts.append(f"偏好：{mentioned[-1]}")  # 只显示最近一条

        return "\n".join(parts) if parts else "【用户信息】可以告诉我更多关于你的信息吗？"

    def build_messages(
        self,
        user_message: str,
        conversation_history: list[dict],
        user_profile: Optional[dict] = None,
        scene_context: Optional[SceneContext] = None,
        task_state: Optional[TaskState] = None,
    ) -> list[dict]:
        messages = []

        system_content = self.build_system_prompt(user_profile, scene_context, task_state)
        messages.append({"role": "system", "content": system_content})

        messages.extend(conversation_history)

        if user_message:
            messages.append({"role": "user", "content": user_message})

        return messages


prompt_builder = PromptBuilder()
