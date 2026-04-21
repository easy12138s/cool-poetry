from .base import Skill


class GameSkill(Skill):
    name = "game"
    description = "诗词游戏技能框架"
    tool_whitelist = ["record_activity_state", "get_user_profile", "update_user_profile", "search_poem", "get_poem_detail"]
    activation_signals = ["飞花令", "诗词接龙", "填空", "游戏", "对诗", "玩"]
    exit_signals = ["不玩了", "退出游戏", "结束游戏", "换个话题"]

    def get_prompt_extension(self) -> str:
        return """
# 技能模式：诗词游戏

你正在和孩子玩诗词游戏！以下是游戏主持指南：

## 游戏状态管理
- 每次你的回复中，必须使用 record_activity_state 工具更新游戏状态
- 游戏进行中时，保持热情和鼓励，不要太难
- 游戏结束后，使用 record_learning_progress 记录孩子在这个游戏中表现的诗词

## 主持风格
- 像一个有趣的游戏主持人，先说明规则，再开始
- 每一轮给出清晰的指令和鼓励
- 如果孩子答错，温柔地给出正确答案，然后继续
- 适时夸奖："太厉害了！""你真是个小诗人！"

## 游戏结束条件
- 孩子说"不玩了"或"退出游戏"时，优雅地结束游戏，总结成绩
- 游戏进行 5-10 轮后，可以主动询问是否继续
- 结束时回顾表现，给予鼓励和奖励

## 当前游戏信息

{game_context}

## 重要提醒
- 你自身拥有丰富的古诗词知识，出题和判断答案时优先使用自身知识
- 仅在需要精确验证某首诗的原文时使用 search_poem 工具
- 游戏的目的是让孩子在快乐中学习，不要让难度打击到孩子"""

    def build_dynamic_context(self, state: dict) -> dict:
        game_state = state.get("game_state", {})
        if not game_state or game_state.get("status") != "active":
            return {"game_context": "当前没有进行中的游戏，可以询问孩子想玩什么游戏。"}

        game_type = game_state.get("game_type", "未知")
        current_round = game_state.get("current_round", 0)
        score = game_state.get("score", 0)
        history = game_state.get("history", [])

        history_text = ""
        if history:
            recent = history[-3:]
            history_text = "\n最近几轮：\n" + "\n".join(
                f"  第{h.get('round', '?')}轮：{h.get('summary', '')}"
                for h in recent
            )

        context = f"""正在进行的游戏：{game_type}
当前轮次：第{current_round}轮
得分：{score}分{history_text}"""
        return {"game_context": context}

    def is_sticky(self, state: dict, user_message: str) -> bool:
        active_game = state.get("game_state", {}).get("status") == "active"
        if not active_game:
            return False
        return not any(s in user_message for s in self.exit_signals)

    def on_activate(self, state: dict) -> dict:
        state["skill_name"] = "game"
        if not state.get("game_state"):
            state["game_state"] = {
                "status": "active",
                "game_type": "",
                "current_round": 0,
                "score": 0,
                "history": [],
                "context": {},
            }
        else:
            state["game_state"]["status"] = "active"
        return state

    def on_deactivate(self, state: dict) -> dict:
        if "game_state" in state:
            state["game_state"]["status"] = "completed"
        return state
