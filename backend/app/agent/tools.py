import json
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
    query = (
        select(Poem)
        .options(selectinload(Poem.author), selectinload(Poem.paragraphs))
        .where(Poem.is_for_children == True)
    )

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
    poems = result.scalars().all()

    if not poems:
        return "没有找到匹配的诗词。"

    output = []
    for poem in poems:
        author_name = poem.author.name if poem.author else "未知"
        content = "".join([p.content for p in poem.paragraphs])
        output.append(
            f"《{poem.title}》 - {author_name}\n{content}\n难度：{poem.difficulty}/5"
        )

    return "\n\n".join(output)


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
    query = (
        select(Poem)
        .options(selectinload(Poem.author), selectinload(Poem.paragraphs))
        .where(Poem.id == poem_id)
    )
    result = await db.execute(query)
    poem = result.scalar_one_or_none()

    if not poem:
        return "未找到该诗词。"

    author_name = poem.author.name if poem.author else "未知"
    content = "\n".join([p.content for p in poem.paragraphs])

    detail = f"""《{poem.title}》
作者：{author_name}（{poem.author.dynasty if poem.author and poem.author.dynasty else "朝代不详"}）

【原文】
{content}"""

    if poem.translation:
        detail += f"\n\n【译文】\n{poem.translation}"

    if poem.appreciation:
        detail += f"\n\n【赏析】\n{poem.appreciation}"

    return detail


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
    query = (
        select(Poem)
        .options(selectinload(Poem.author), selectinload(Poem.paragraphs))
        .where(Poem.is_for_children == True)
    )

    if difficulty:
        query = query.where(Poem.difficulty <= difficulty)

    query = query.order_by(func.rand()).limit(1)
    result = await db.execute(query)
    poem = result.scalar_one_or_none()

    if not poem:
        return "暂时没有找到合适的诗词。"

    author_name = poem.author.name if poem.author else "未知"
    content = "".join([p.content for p in poem.paragraphs])

    return f"《{poem.title}》 - {author_name}\n{content}"


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
    query = select(Author).where(Author.name.contains(name))
    result = await db.execute(query)
    author = result.scalar_one_or_none()

    if not author:
        return f"未找到诗人 {name} 的信息。"

    poem_query = (
        select(Poem)
        .where(Poem.author_id == author.id)
        .limit(5)
    )
    poem_result = await db.execute(poem_query)
    poems = poem_result.scalars().all()

    info = f"""【{author.name}】
朝代：{author.dynasty or "不详"}
简介：{author.description or "暂无简介"}

代表作品：
"""
    for poem in poems:
        info += f"- 《{poem.title}》\n"

    return info
