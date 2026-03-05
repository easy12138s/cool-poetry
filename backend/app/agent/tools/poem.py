import json
import random
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...models import Author, Poem
from .base import tool


def _estimate_difficulty(content: str) -> int:
    """基于诗词长度和生僻字估算难度"""
    length = len(content)
    
    # 基础难度判断（基于长度）
    if length <= 20:  # 五言绝句
        base_difficulty = 1
    elif length <= 28:  # 七言绝句
        base_difficulty = 2
    elif length <= 40:  # 五言律诗
        base_difficulty = 3
    elif length <= 56:  # 七言律诗
        base_difficulty = 4
    else:  # 长诗
        base_difficulty = 5
    
    # 可以在这里添加生僻字检测逻辑
    # rare_chars = ['曦', '曦', '曦', ...]  # 生僻字列表
    # rare_count = sum(1 for char in content if char in rare_chars)
    # if rare_count > 3:
    #     base_difficulty = min(5, base_difficulty + 1)
    
    return base_difficulty


@tool(
    name="search_poem",
    description="""搜索古诗词作品，包括唐诗、宋词、元曲等。

可搜索的内容包括：
- 唐诗：如李白、杜甫的诗歌
- 宋词：如苏轼、李清照的词作  
- 元曲：如马致远、关汉卿的散曲
- 其他古典文学作品

支持按关键词、作者、类别搜索。""",
    parameters={
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "搜索关键词，可以是作品标题，如'静夜思'、'明月'",
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
    limit: int = 5,
) -> str:
    """搜索古诗词作品，包括唐诗、宋词、元曲等。
    
    注意：由于数据库中 is_for_children、scene_tags、difficulty 字段为空或默认值，
    已移除这些无效过滤条件。
    """

    query = (
        select(Poem)
        .options(selectinload(Poem.author), selectinload(Poem.paragraphs))
    )

    # 按类别过滤（有值）
    if category:
        query = query.where(Poem.category == category)

    # 只在 title 中搜索（notes 字段可能为空）
    if keyword:
        query = query.where(Poem.title.contains(keyword))

    # 通过 author 表关联查询
    if author:
        author_query = select(Author.id).where(Author.name.contains(author))
        author_result = await db.execute(author_query)
        author_ids = [a[0] for a in author_result.fetchall()]
        if author_ids:
            query = query.where(Poem.author_id.in_(author_ids))

    query = query.limit(limit)
    result = await db.execute(query)
    poems = result.scalars().all()

    if not poems:
        return json.dumps({
            "success": False,
            "data": None,
            "message": f"没有找到包含'{keyword or author}'的诗词。",
            "suggestions": ["尝试关键词：月亮、春天、花、山、水", "尝试诗人：李白、杜甫、白居易、王维"]
        }, ensure_ascii=False)

    output = []
    for poem in poems:
        author_name = poem.author.name if poem.author else "未知"
        content = "".join([p.content for p in poem.paragraphs])
        # 动态计算难度（数据库中可能为默认值）
        difficulty = poem.difficulty if poem.difficulty and poem.difficulty != 3 else _estimate_difficulty(content)
        
        output.append({
            "id": poem.id,
            "title": poem.title,
            "author": author_name,
            "content": content,
            "difficulty": difficulty,
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
    """获取古诗词作品的详细信息。
    
    注意：translation、appreciation 字段可能为空，会返回友好提示。
    difficulty 字段会动态计算。
    """
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
    
    # 动态计算难度
    difficulty = poem.difficulty if poem.difficulty and poem.difficulty != 3 else _estimate_difficulty(content)

    detail = {
        "id": poem.id,
        "title": poem.title,
        "author": author_name,
        "dynasty": poem.author.dynasty if poem.author and poem.author.dynasty else "朝代不详",
        "content": content,
        # 处理可能为空的字段
        "translation": poem.translation or "暂无译文，小诗仙可以为你讲解这首诗的意思哦~",
        "appreciation": poem.appreciation or "暂无赏析，你想听听这首诗的妙处吗？",
        "difficulty": difficulty,
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

可以指定类别获取特定类型的作品。""",
    parameters={
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["tang_poem", "song_ci", "song_poem", "yuanqu", "imperial_tang"],
                "description": "作品类别，不指定则随机选择",
            },
        },
    },
)
async def get_random_poem(
    db: AsyncSession,
    category: Optional[str] = None,
) -> str:
    """随机获取一首古诗词作品。
    
    注意：已移除 difficulty 过滤（数据库中该字段为默认值）。
    """
    query = (
        select(Poem)
        .options(selectinload(Poem.author), selectinload(Poem.paragraphs))
    )

    # 只保留 category 过滤
    if category:
        query = query.where(Poem.category == category)

    result = await db.execute(query)
    poems = result.scalars().all()

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
    
    # 动态计算难度
    difficulty = poem.difficulty if poem.difficulty and poem.difficulty != 3 else _estimate_difficulty(content)

    result = {
        "id": poem.id,
        "title": poem.title,
        "author": author_name,
        "content": content,
        "difficulty": difficulty,
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
    description="""获取文学家的详细信息，包括生平简介、代表作品和创作统计。

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
    """获取文学家的详细信息，包括统计信息。"""
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

    # 获取诗人的所有诗词
    poem_query = (
        select(Poem)
        .options(selectinload(Poem.paragraphs))
        .where(Poem.author_id == author.id)
    )
    poem_result = await db.execute(poem_query)
    poems = poem_result.scalars().all()

    # 统计诗词类别分布
    category_stats = {}
    for poem in poems:
        cat = poem.category or "未知"
        category_stats[cat] = category_stats.get(cat, 0) + 1

    # 构建代表作品列表（包含内容预览）
    representative_works = []
    for poem in poems[:5]:
        content = "".join([p.content for p in poem.paragraphs])
        representative_works.append({
            "id": poem.id,
            "title": poem.title,
            "preview": content[:30] + "..." if len(content) > 30 else content,
            "category": poem.category,
        })

    result = {
        "id": author.id,
        "name": author.name,
        "dynasty": author.dynasty or "不详",
        "description": author.description or f"{author.name}是{author.dynasty or '古代'}著名诗人，留下了许多脍炙人口的诗篇。",
        "poem_count": len(poems),
        "category_distribution": category_stats,
        "representative_works": representative_works,
    }

    return json.dumps({
        "success": True,
        "data": result,
        "message": f"诗人 {author.name} 信息"
    }, ensure_ascii=False)
