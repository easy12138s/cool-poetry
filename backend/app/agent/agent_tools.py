import json
import random
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .base import tool
from ..models import Author, Poem, Paragraph


@tool(
    name="search_poem",
    description="搜索诗词，可以根据关键词、作者或场景标签搜索。返回匹配的诗词列表。",
    parameters={
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "搜索关键词，可以是诗词标题或内容中的词",
            },
            "author": {
                "type": "string",
                "description": "诗人姓名，如李白、杜甫",
            },
            "scene_tag": {
                "type": "string",
                "description": "场景标签，如春天、月亮、思乡、送别",
            },
            "difficulty": {
                "type": "integer",
                "description": "难度等级 1-5，1最简单",
            },
            "limit": {
                "type": "integer",
                "description": "返回结果数量限制，默认5",
            },
        },
    },
)
async def search_poem(
    db: AsyncSession,
    keyword: Optional[str] = None,
    author: Optional[str] = None,
    scene_tag: Optional[str] = None,
    difficulty: Optional[int] = None,
    limit: int = 5,
) -> str:
    """搜索诗词，优先返回适合儿童的诗词，如果没有则返回其他诗词。"""

    async def _do_search(for_children_only: bool = True):
        query = (
            select(Poem)
            .options(selectinload(Poem.author), selectinload(Poem.paragraphs))
        )

        if for_children_only:
            query = query.where(Poem.is_for_children == True)

        if keyword:
            query = query.where(
                (Poem.title.contains(keyword)) | (Poem.notes.contains(keyword))
            )

        if author:
            author_query = select(Author.id).where(Author.name.contains(author))
            author_result = await db.execute(author_query)
            author_ids = [a[0] for a in author_result.fetchall()]
            if author_ids:
                query = query.where(Poem.author_id.in_(author_ids))

        if scene_tag:
            query = query.where(Poem.scene_tags.contains(f'"{scene_tag}"'))

        if difficulty:
            query = query.where(Poem.difficulty <= difficulty)

        query = query.limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    # 先尝试搜索适合儿童的诗词
    poems = await _do_search(for_children_only=True)

    # 如果没有找到，尝试搜索所有诗词
    if not poems:
        poems = await _do_search(for_children_only=False)

    if not poems:
        return json.dumps({
            "success": False,
            "data": None,
            "message": f"没有找到包含'{keyword or author or scene_tag}'的诗词。",
            "suggestions": ["尝试关键词：月亮、春天、花、山、水", "尝试诗人：李白、杜甫、白居易、王维"]
        }, ensure_ascii=False)

    output = []
    for poem in poems:
        author_name = poem.author.name if poem.author else "未知"
        content = "".join([p.content for p in poem.paragraphs])
        output.append({
            "id": poem.id,
            "title": poem.title,
            "author": author_name,
            "content": content,
            "difficulty": poem.difficulty,
            "is_for_children": poem.is_for_children
        })

    return json.dumps({
        "success": True,
        "data": output,
        "message": f"找到 {len(poems)} 首诗词"
    }, ensure_ascii=False)


@tool(
    name="get_poem_detail",
    description="获取诗词详情，包括原文、译文、赏析等信息。",
    parameters={
        "type": "object",
        "properties": {
            "poem_id": {
                "type": "integer",
                "description": "诗词ID",
            },
        },
        "required": ["poem_id"],
    },
)
async def get_poem_detail(db: AsyncSession, poem_id: int) -> str:
    """获取诗词详情。"""
    query = (
        select(Poem)
        .options(selectinload(Poem.author), selectinload(Poem.paragraphs))
        .where(Poem.id == poem_id)
    )
    result = await db.execute(query)
    poem = result.scalar_one_or_none()

    if not poem:
        return json.dumps({
            "success": False,
            "data": None,
            "message": f"未找到ID为 {poem_id} 的诗词。"
        }, ensure_ascii=False)

    author_name = poem.author.name if poem.author else "未知"
    content = "\n".join([p.content for p in poem.paragraphs])

    detail = {
        "id": poem.id,
        "title": poem.title,
        "author": author_name,
        "dynasty": poem.author.dynasty if poem.author and poem.author.dynasty else "朝代不详",
        "content": content,
        "translation": poem.translation,
        "appreciation": poem.appreciation,
        "difficulty": poem.difficulty,
    }

    return json.dumps({
        "success": True,
        "data": detail,
        "message": f"《{poem.title}》详情"
    }, ensure_ascii=False)


@tool(
    name="get_random_poem",
    description="随机获取一首适合儿童的诗词，可以指定难度等级。",
    parameters={
        "type": "object",
        "properties": {
            "difficulty": {
                "type": "integer",
                "description": "难度等级 1-5，默认随机",
            },
        },
    },
)
async def get_random_poem(db: AsyncSession, difficulty: Optional[int] = None) -> str:
    """随机获取一首诗词。使用 Python 随机选择，避免数据库函数兼容性问题。"""

    async def _get_poems(for_children_only: bool = True):
        query = (
            select(Poem)
            .options(selectinload(Poem.author), selectinload(Poem.paragraphs))
        )

        if for_children_only:
            query = query.where(Poem.is_for_children == True)

        if difficulty:
            query = query.where(Poem.difficulty <= difficulty)

        result = await db.execute(query)
        return result.scalars().all()

    # 先尝试获取适合儿童的诗词
    poems = await _get_poems(for_children_only=True)

    # 如果没有找到，尝试获取所有诗词
    if not poems:
        poems = await _get_poems(for_children_only=False)

    if not poems:
        return json.dumps({
            "success": False,
            "data": None,
            "message": "数据库中暂时没有合适的诗词。",
            "suggestions": ["联系管理员添加诗词数据"]
        }, ensure_ascii=False)

    # 使用 Python random 随机选择一首
    poem = random.choice(poems)

    author_name = poem.author.name if poem.author else "未知"
    content = "".join([p.content for p in poem.paragraphs])

    result = {
        "id": poem.id,
        "title": poem.title,
        "author": author_name,
        "content": content,
        "difficulty": poem.difficulty,
        "dynasty": poem.author.dynasty if poem.author and poem.author.dynasty else "朝代不详",
    }

    return json.dumps({
        "success": True,
        "data": result,
        "message": f"随机推荐：《{poem.title}》"
    }, ensure_ascii=False)


@tool(
    name="get_author_info",
    description="获取诗人的详细信息，包括生平简介和代表作品。",
    parameters={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "诗人姓名",
            },
        },
        "required": ["name"],
    },
)
async def get_author_info(db: AsyncSession, name: str) -> str:
    """获取诗人信息。"""
    query = select(Author).where(Author.name.contains(name))
    result = await db.execute(query)
    author = result.scalar_one_or_none()

    if not author:
        return json.dumps({
            "success": False,
            "data": None,
            "message": f"未找到诗人 {name} 的信息。",
            "suggestions": ["尝试：李白、杜甫、白居易、王维、苏轼"]
        }, ensure_ascii=False)

    poem_query = (
        select(Poem)
        .where(Poem.author_id == author.id)
        .limit(5)
    )
    poem_result = await db.execute(poem_query)
    poems = poem_result.scalars().all()

    result = {
        "id": author.id,
        "name": author.name,
        "dynasty": author.dynasty or "不详",
        "description": author.description or "暂无简介",
        "representative_works": [poem.title for poem in poems]
    }

    return json.dumps({
        "success": True,
        "data": result,
        "message": f"诗人 {author.name} 信息"
    }, ensure_ascii=False)


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
    from ..models.user_profile import UserProfile

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
    from ..models.user_profile import UserProfile

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
    from ..models.user_profile import UserProfile

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
