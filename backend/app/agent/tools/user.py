import json
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.user_profile import UserProfile
from .base import tool


@tool(
    name="update_user_profile",
    description="更新用户画像信息。当孩子提供昵称、年龄、喜欢的诗人等信息时调用。",
    parameters={
        "type": "object",
        "properties": {
            "nickname": {"type": "string", "description": "孩子的昵称"},
            "age": {"type": "integer", "description": "孩子的年龄"},
            "favorite_poet": {"type": "string", "description": "孩子喜欢的诗人姓名，如'李白'"},
            "preference": {"type": "string", "description": "孩子的偏好，如'喜欢写景的诗'、'喜欢短诗'"},
        },
    },
)
async def update_user_profile(
    db: AsyncSession,
    user_id: str,
    nickname: Optional[str] = None,
    age: Optional[int] = None,
    favorite_poet: Optional[str] = None,
    preference: Optional[str] = None,
) -> str:
    """更新用户画像"""
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        profile = UserProfile(user_id=user_id)
        db.add(profile)

    updated_fields = []

    if nickname:
        profile.nickname = nickname
        updated_fields.append(f"昵称：{nickname}")

    if age:
        profile.age = age
        updated_fields.append(f"年龄：{age}岁")

    if favorite_poet:
        current_poets = profile.favorite_poets or []
        if favorite_poet not in current_poets:
            current_poets.append(favorite_poet)
            profile.favorite_poets = current_poets
            updated_fields.append(f"喜欢的诗人：{favorite_poet}")

    if preference:
        prefs = profile.preferences or {}
        if "mentioned" not in prefs:
            prefs["mentioned"] = []
        prefs["mentioned"].append(preference)
        profile.preferences = prefs
        updated_fields.append(f"偏好：{preference}")

    await db.commit()

    return json.dumps({
        "success": True,
        "message": "已记住你的信息啦！",
        "updated": updated_fields
    }, ensure_ascii=False)


@tool(
    name="get_user_profile",
    description="获取用户的完整画像信息，包括学习进度、喜欢的诗词等详细信息。当需要了解孩子的学习情况时调用。",
    parameters={
        "type": "object",
        "properties": {},
    },
)
async def get_user_profile(db: AsyncSession, user_id: str) -> str:
    """获取用户完整画像"""
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        return json.dumps({
            "success": False,
            "message": "还没有你的信息呢，可以告诉我你的名字和年龄吗？"
        }, ensure_ascii=False)

    data = profile.to_dict()

    # 格式化学习进度
    progress_info = []
    learning_progress = data.get("learning_progress", {})
    if isinstance(learning_progress, dict):
        total = learning_progress.get("total_learned", 0)
        poems_learned = learning_progress.get("poems_learned", [])

        progress_info.append(f"已学诗词：{total}首")

        if poems_learned:
            # 按掌握程度分类
            mastered = [p for p in poems_learned if isinstance(p, dict) and p.get("mastery_level", 0) >= 4]
            learning = [p for p in poems_learned if isinstance(p, dict) and p.get("mastery_level", 0) < 4]

            if mastered:
                mastered_titles = [p.get("title", "") for p in mastered[-5:]]
                progress_info.append(f"已掌握：{'、'.join(mastered_titles)}")

            if learning:
                learning_titles = [p.get("title", "") for p in learning[-3:]]
                progress_info.append(f"学习中：{'、'.join(learning_titles)}")

    # 格式化偏好
    prefs_info = []
    preferences = data.get("preferences", {})
    if isinstance(preferences, dict):
        mentioned = preferences.get("mentioned", [])
        if mentioned:
            prefs_info.append(f"偏好：{', '.join(mentioned[-3:])}")

    return json.dumps({
        "success": True,
        "data": {
            "nickname": data.get("nickname"),
            "age": data.get("age"),
            "favorite_poets": data.get("favorite_poets", []),
            "favorite_poems": data.get("favorite_poems", []),
            "progress_summary": progress_info,
            "preferences_summary": prefs_info,
        },
        "message": "获取用户画像成功"
    }, ensure_ascii=False)


@tool(
    name="record_learning_progress",
    description="记录孩子的学习进度，包括学会了哪些诗、掌握程度。",
    parameters={
        "type": "object",
        "properties": {
            "poem_id": {"type": "integer", "description": "诗词ID"},
            "poem_title": {"type": "string", "description": "诗词标题"},
            "mastery_level": {"type": "integer", "description": "掌握程度 1-5，5为完全掌握"},
            "notes": {"type": "string", "description": "学习笔记，如'能背诵'、'理解大意'"},
        },
        "required": ["poem_id", "poem_title"],
    },
)
async def record_learning_progress(
    db: AsyncSession,
    user_id: str,
    poem_id: int,
    poem_title: str,
    mastery_level: int = 1,
    notes: Optional[str] = None,
) -> str:
    """记录学习进度"""
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        profile = UserProfile(user_id=user_id)
        db.add(profile)

    progress = profile.learning_progress or {}
    poems_learned = progress.get("poems_learned", [])

    poem_record = {
        "poem_id": poem_id,
        "poem_title": poem_title,
        "mastery_level": mastery_level,
        "notes": notes,
    }

    existing = next((p for p in poems_learned if p["poem_id"] == poem_id), None)
    if existing:
        existing.update(poem_record)
    else:
        poems_learned.append(poem_record)

    progress["poems_learned"] = poems_learned
    progress["total_learned"] = len(poems_learned)
    profile.learning_progress = progress

    await db.commit()

    return json.dumps({
        "success": True,
        "message": f"已记录《{poem_title}》的学习进度！",
        "total_learned": len(poems_learned)
    }, ensure_ascii=False)
