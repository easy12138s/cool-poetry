import json
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.user_profile import UserProfile
from .base import tool

logger = logging.getLogger(__name__)


@tool(
    name="analyze_conversation",
    description="分析对话历史，提取关键信息如诗词、诗人、用户兴趣等",
    parameters={
        "type": "object",
        "properties": {
            "messages": {
                "type": "array",
                "items": {"type": "object"},
                "description": "要分析的对话消息列表",
            },
            "focus": {
                "type": "string",
                "description": "分析焦点：poems(诗词)、poets(诗人)、interests(兴趣)、all(全部)",
            },
        },
        "required": ["messages"],
    },
)
async def analyze_conversation(
    db: AsyncSession,
    messages: list[dict],
    focus: str = "all",
    **kwargs,
) -> str:
    result = {
        "key_poems": [],
        "key_poets": [],
        "user_interests": [],
        "sentiment": "neutral",
    }

    all_text = " ".join(
        [msg.get("content", "") for msg in messages if msg.get("content")]
    )

    poem_keywords = ["静夜思", "春晓", "登鹳雀楼", "望庐山瀑布", "早发白帝城", "将进酒", "水调歌头"]
    poet_keywords = ["李白", "杜甫", "白居易", "王维", "苏轼", "辛弃疾", "李清照"]

    for keyword in poem_keywords:
        if keyword in all_text:
            result["key_poems"].append(keyword)

    for keyword in poet_keywords:
        if keyword in all_text:
            result["key_poets"].append(keyword)

    interest_keywords = {
        "山水": "山水田园",
        "思乡": "思乡怀人",
        "送别": "送别友情",
        "战争": "边塞军旅",
        "爱情": "爱情闺怨",
    }
    for keyword, interest in interest_keywords.items():
        if keyword in all_text:
            result["user_interests"].append(interest)

    positive_words = ["喜欢", "好", "棒", "美", "太好了", "厉害"]
    negative_words = ["不喜欢", "难", "无聊", "不懂"]

    positive_count = sum(1 for w in positive_words if w in all_text)
    negative_count = sum(1 for w in negative_words if w in all_text)

    if positive_count > negative_count:
        result["sentiment"] = "positive"
    elif negative_count > positive_count:
        result["sentiment"] = "negative"

    return json.dumps(result, ensure_ascii=False)


@tool(
    name="update_user_profile",
    description="更新用户画像信息，如喜欢的诗人、诗词、兴趣等",
    parameters={
        "type": "object",
        "properties": {
            "favorite_poets": {
                "type": "array",
                "items": {"type": "string"},
                "description": "喜欢的诗人列表",
            },
            "favorite_poems": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "喜欢的诗词ID列表",
            },
            "interests": {
                "type": "array",
                "items": {"type": "string"},
                "description": "兴趣标签列表",
            },
        },
        "required": [],
    },
)
async def update_user_profile(
    db: AsyncSession,
    user_id: Optional[str] = None,
    favorite_poets: Optional[list[str]] = None,
    favorite_poems: Optional[list[int]] = None,
    interests: Optional[list[str]] = None,
    **kwargs,
) -> str:
    if not user_id:
        return json.dumps({"success": False, "error": "缺少 user_id"}, ensure_ascii=False)

    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        profile = UserProfile(user_id=user_id)
        db.add(profile)

    if favorite_poets:
        current_poets = profile.favorite_poets or []
        profile.favorite_poets = list(set(current_poets + favorite_poets))

    if favorite_poems:
        current_poems = profile.favorite_poems or []
        profile.favorite_poems = list(set(current_poems + favorite_poems))

    if interests:
        current_progress = profile.learning_progress or {}
        current_interests = current_progress.get("interests", [])
        current_progress["interests"] = list(set(current_interests + interests))
        profile.learning_progress = current_progress

    await db.commit()

    return json.dumps(
        {
            "success": True,
            "message": "用户画像已更新",
            "profile": {
                "favorite_poets": profile.favorite_poets,
                "favorite_poems": profile.favorite_poems,
            },
        },
        ensure_ascii=False,
    )


@tool(
    name="extract_entities",
    description="从文本中提取关键实体，如诗词名、诗人名、关键词等",
    parameters={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "要提取实体的文本",
            },
        },
        "required": ["text"],
    },
)
async def extract_entities(
    db: AsyncSession,
    text: str,
    **kwargs,
) -> str:
    entities = {
        "poems": [],
        "poets": [],
        "keywords": [],
    }

    poem_patterns = [
        "静夜思", "春晓", "登鹳雀楼", "望庐山瀑布", "早发白帝城",
        "将进酒", "水调歌头", "念奴娇", "沁园春", "满江红",
        "出塞", "凉州词", "芙蓉楼送辛渐", "九月九日忆山东兄弟",
    ]

    poet_patterns = [
        "李白", "杜甫", "白居易", "王维", "苏轼", "辛弃疾", "李清照",
        "王昌龄", "杜牧", "李商隐", "孟浩然", "柳宗元", "韩愈",
    ]

    for poem in poem_patterns:
        if poem in text:
            entities["poems"].append(poem)

    for poet in poet_patterns:
        if poet in text:
            entities["poets"].append(poet)

    keyword_patterns = [
        "月亮", "春天", "秋天", "山水", "思乡", "送别",
        "战争", "爱情", "友情", "田园", "边塞", "江南",
    ]

    for keyword in keyword_patterns:
        if keyword in text:
            entities["keywords"].append(keyword)

    return json.dumps(entities, ensure_ascii=False)
