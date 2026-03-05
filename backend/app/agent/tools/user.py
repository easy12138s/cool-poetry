import json
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.user_profile import UserProfile
from .base import tool


@tool(
    name="update_user_profile",
    description="""更新用户画像信息。支持更新昵称、年龄、喜欢的诗人列表、偏好。

使用建议：
1. 先调用 get_user_profile 查询已有信息
2. 根据已有信息决定是添加新数据还是覆盖旧数据
3. 对于列表类型的字段（favorite_poets、add_preferences），会追加到已有列表
4. 对于单值字段（nickname、age），会直接覆盖旧值""",
    parameters={
        "type": "object",
        "properties": {
            "nickname": {"type": "string", "description": "孩子的昵称，2-20个字符，覆盖旧值"},
            "age": {"type": "integer", "description": "孩子的年龄，6-12岁，覆盖旧值", "minimum": 6, "maximum": 12},
            "favorite_poets": {"type": "array", "items": {"type": "string"}, "description": "喜欢的诗人列表，如['李白', '杜甫']，会追加到已有列表"},
            "add_preferences": {"type": "array", "items": {"type": "string"}, "description": "要添加的偏好列表，如['喜欢写景的诗', '喜欢短诗']"},
            "remove_preferences": {"type": "array", "items": {"type": "string"}, "description": "要移除的偏好列表"},
        },
    },
)
async def update_user_profile(
    db: AsyncSession,
    user_id: str,
    nickname: Optional[str] = None,
    age: Optional[int] = None,
    favorite_poets: Optional[list] = None,
    add_preferences: Optional[list] = None,
    remove_preferences: Optional[list] = None,
) -> str:
    """更新用户画像 - 优化版本
    
    改进点：
    1. 支持批量更新诗人列表
    2. 支持添加和移除偏好
    3. 添加年龄范围验证
    4. 添加昵称长度验证
    """
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        profile = UserProfile(user_id=user_id)
        db.add(profile)

    updated_fields = []

    # 更新昵称（验证长度）
    if nickname is not None:
        if len(nickname) < 2 or len(nickname) > 20:
            return json.dumps({
                "success": False,
                "message": "昵称长度需要在2-20个字符之间"
            }, ensure_ascii=False)
        profile.nickname = nickname
        updated_fields.append(f"昵称：{nickname}")

    # 更新年龄（验证范围）
    if age is not None:
        if age < 6 or age > 12:
            return json.dumps({
                "success": False,
                "message": "年龄需要在6-12岁之间"
            }, ensure_ascii=False)
        profile.age = age
        updated_fields.append(f"年龄：{age}岁")

    # 批量更新喜欢的诗人（追加模式，自动去重）
    if favorite_poets is not None and isinstance(favorite_poets, list):
        current_poets = profile.favorite_poets or []
        new_poets = [p for p in favorite_poets if p not in current_poets]
        if new_poets:
            current_poets.extend(new_poets)
            profile.favorite_poets = current_poets
            updated_fields.append(f"新增喜欢的诗人：{', '.join(new_poets)}")

    # 更新偏好（支持添加和移除）
    if add_preferences is not None or remove_preferences is not None:
        prefs = profile.preferences or {}
        if "mentioned" not in prefs:
            prefs["mentioned"] = []
        
        # 添加新偏好
        if add_preferences is not None and isinstance(add_preferences, list):
            new_prefs = [p for p in add_preferences if p not in prefs["mentioned"]]
            if new_prefs:
                prefs["mentioned"].extend(new_prefs)
                updated_fields.append(f"新增偏好：{', '.join(new_prefs)}")
        
        # 移除偏好
        if remove_preferences is not None and isinstance(remove_preferences, list):
            removed = []
            for p in remove_preferences:
                if p in prefs["mentioned"]:
                    prefs["mentioned"].remove(p)
                    removed.append(p)
            if removed:
                updated_fields.append(f"移除偏好：{', '.join(removed)}")
        
        profile.preferences = prefs

    await db.commit()

    if not updated_fields:
        return json.dumps({
            "success": True,
            "message": "没有需要更新的信息",
            "updated": []
        }, ensure_ascii=False)

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
