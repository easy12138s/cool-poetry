import json
import random
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...models import Author, Poem
from .base import tool


@tool(
    name="search_poem",
    description="""搜索古诗词作品，包括唐诗、宋词、元曲等。

可搜索的内容包括：
- 唐诗：如李白、杜甫的诗歌
- 宋词：如苏轼、李清照的词作  
- 元曲：如马致远、关汉卿的散曲
- 其他古典文学作品

支持按关键词、作者、类别、场景标签搜索。""",
    parameters={
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "搜索关键词，可以是作品标题或内容中的词，如'静夜思'、'明月'",
            },
            "author": {
                "type": "string",
                "description": "作者姓名，如李白、杜甫、苏轼、李清照",
            },
            "category": {
                "type": "string",
                "enum": ["tang_poem", "song_ci", "song_poem", "yuanqu", "imperial_tang"],
                "description": "作品类别：tang_poem(唐诗)、song_ci(宋词)、song_poem(宋诗)、yuanqu(元曲)、imperial_tang(宫廷唐诗)",
            },
            "scene_tag": {
                "type": "string",
                "description": "场景标签，如春天、月亮、思乡、送别、山水、边塞",
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
    category: Optional[str] = None,
    scene_tag: Optional[str] = None,
    difficulty: Optional[int] = None,
    limit: int = 5,
) -> str:
    """搜索古诗词作品，包括唐诗、宋词、元曲等。"""

    async def _do_search(for_children_only: bool = True):
        query = (
            select(Poem)
            .options(selectinload(Poem.author), selectinload(Poem.paragraphs))
        )

        if for_children_only:
            query = query.where(Poem.is_for_children == True)

        # 按类别过滤
        if category:
            query = query.where(Poem.category == category)

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
            "is_for_children": poem.is_for_children,
            "category": poem.category,
        })

    return json.dumps({
        "success": True,
        "data": output,
        "message": f"找到 {len(poems)} 首诗词"
    }, ensure_ascii=False)


@tool(
    name="get_poem_detail",
    description="""获取古诗词作品的详细信息，包括原文、译文、赏析等。

支持查看：
- 唐诗的格律和意境
- 宋词的词牌和韵味
- 元曲的曲牌和风格
- 作品的创作背景和赏析""",
    parameters={
        "type": "object",
        "properties": {
            "poem_id": {
                "type": "integer",
                "description": "作品ID",
            },
        },
        "required": ["poem_id"],
    },
)
async def get_poem_detail(db: AsyncSession, poem_id: int) -> str:
    """获取古诗词作品的详细信息。"""
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
        "category": poem.category,
    }

    return json.dumps({
        "success": True,
        "data": detail,
        "message": f"《{poem.title}》详情"
    }, ensure_ascii=False)


@tool(
    name="get_random_poem",
    description="""随机获取一首古诗词作品，包括唐诗、宋词、元曲等。

可获取的类别：
- 唐诗：李白、杜甫等唐代诗人的作品
- 宋词：苏轼、李清照等宋代词人的作品
- 元曲：马致远、关汉卿等元代曲作家的作品

可以指定难度等级获取适合的作品。""",
    parameters={
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["tang_poem", "song_ci", "song_poem", "yuanqu", "imperial_tang"],
                "description": "作品类别，不指定则随机选择",
            },
            "difficulty": {
                "type": "integer",
                "description": "难度等级 1-5，默认随机",
            },
        },
    },
)
async def get_random_poem(
    db: AsyncSession,
    category: Optional[str] = None,
    difficulty: Optional[int] = None,
) -> str:
    """随机获取一首古诗词作品。"""

    async def _get_poems(for_children_only: bool = True):
        query = (
            select(Poem)
            .options(selectinload(Poem.author), selectinload(Poem.paragraphs))
        )

        if for_children_only:
            query = query.where(Poem.is_for_children == True)

        # 按类别过滤
        if category:
            query = query.where(Poem.category == category)

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
        "category": poem.category,
    }

    return json.dumps({
        "success": True,
        "data": result,
        "message": f"随机推荐：《{poem.title}》"
    }, ensure_ascii=False)


@tool(
    name="get_author_info",
    description="""获取文学家的详细信息，包括生平简介和代表作品。

涵盖：
- 唐代诗人：李白、杜甫、白居易等
- 宋代词人：苏轼、李清照、辛弃疾等
- 元代曲作家：马致远、关汉卿等
- 其他朝代的文学家""",
    parameters={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "文学家姓名，如李白、苏轼、马致远",
            },
        },
        "required": ["name"],
    },
)
async def get_author_info(db: AsyncSession, name: str) -> str:
    """获取文学家的详细信息。"""
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
