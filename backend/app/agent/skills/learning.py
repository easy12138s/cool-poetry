from datetime import date

from .base import Skill


class LearningSkill(Skill):
    name = "learning"
    description = "每日学习推荐技能"
    tool_whitelist = [
        "get_user_profile",
        "record_learning_progress",
        "update_user_profile",
        "search_poem",
        "get_poem_detail",
    ]
    activation_signals = ["学习计划", "今天学什么", "推荐一首", "每日推荐", "复习"]
    exit_signals = ["换个话题", "不想看计划了", "继续聊天"]

    def get_prompt_extension(self) -> str:
        return """
# 技能模式：每日学习推荐

你正在为孩子制定今日的学习推荐！以下是推荐策略：

## 推荐生成流程
1. 首先使用 get_user_profile 获取孩子的完整画像（年龄、已学诗词、偏好）
2. 根据画像信息，用你自身的古诗词知识生成推荐
3. 使用 update_user_profile 将推荐结果保存到 daily_recommendation 字段中
4. 用鼓励和期待的语言告诉孩子今天的计划

## 推荐策略（重要）

- **新诗推荐**：根据年龄选择难度合适的诗
  - 6-7岁：五言绝句（《咏鹅》《静夜思》《春晓》）
  - 8-9岁：七言绝句+五言律诗（《望庐山瀑布》《悯农》）
  - 10-12岁：可尝试较长作品（《将进酒》《水调歌头》）
- **复习推荐**：从已学但掌握程度 < 4 的诗词中选 1-2 首复习
- **游戏推荐**：根据孩子偏好推荐适合的游戏类型
- **避免重复**：不要推荐已经完全掌握（mastery_level >= 4）的诗作为新诗

## 输出格式

推荐完成后，用温暖的语言告诉孩子：
1. 今天的新诗是什么，为什么推荐这首（1-2句话）
2. 要复习哪首诗
3. 可以玩什么游戏
4. 一句鼓励的话

## 重要提醒

- 你自身的古诗词知识已经非常丰富，不需要调用 search_poem 来找诗推荐
- 仅在需要精确验证时使用工具
- 推荐要个性化，不要千篇一律"""

    def build_dynamic_context(self, state: dict) -> dict:
        daily_plan = state.get("daily_plan", {})
        if not daily_plan:
            return {}
        plan_date = daily_plan.get("date", "")
        new_poem = daily_plan.get("new_poem", {})
        review = daily_plan.get("review_poems", [])
        parts = [f"今日推荐日期：{plan_date}"]
        if new_poem:
            parts.append(
                f"今日新诗：《{new_poem.get('title', '')}》- {new_poem.get('author', '')}"
            )
        if review:
            review_titles = "、".join(f"《{r.get('title', '')}》" for r in review[:2])
            parts.append(f"复习诗词：{review_titles}")
        return {"learning_context": "\n".join(parts)}

    def on_activate(self, state: dict) -> dict:
        state["skill_name"] = "learning"
        today = date.today().isoformat()
        if not state.get("daily_plan") or state["daily_plan"].get("date") != today:
            state["daily_plan"] = {"date": today}
        return state

    def on_deactivate(self, state: dict) -> dict:
        return state
