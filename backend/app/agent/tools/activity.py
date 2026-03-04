import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.activity import ActivityState
from .base import tool

logger = logging.getLogger(__name__)


@tool(
    name="record_activity_state",
    description="记录或更新当前正在进行的活动状态。当你和用户开始一个连续的活动（如诗词游戏、学习任务）时，调用此工具记录状态。",
    parameters={
        "type": "object",
        "properties": {
            "activity_type": {
                "type": "string",
                "enum": ["game", "learning", "task"],
                "description": "活动类型：game(游戏)、learning(学习)、task(任务)",
            },
            "activity_name": {
                "type": "string",
                "description": "活动名称，如'诗词接龙'、'飞花令'、'背诵任务'",
            },
            "status": {
                "type": "string",
                "enum": ["active", "paused", "completed", "cancelled"],
                "description": "活动状态：active(进行中)、paused(暂停)、completed(完成)、cancelled(取消)",
            },
            "context": {
                "type": "object",
                "description": "活动上下文，如进度、得分、当前诗词等",
                "properties": {
                    "current_round": {"type": "integer", "description": "当前轮次"},
                    "score": {"type": "integer", "description": "得分"},
                    "current_poem": {"type": "string", "description": "当前诗词"},
                    "current_keyword": {"type": "string", "description": "当前关键词"},
                },
            },
        },
        "required": ["activity_type", "activity_name", "status"],
    },
)
async def record_activity_state(
    db: AsyncSession,
    activity_type: str,
    activity_name: str,
    status: str,
    context: Optional[dict] = None,
    user_id: Optional[str] = None,
    **kwargs,
) -> str:
    if not user_id:
        return json.dumps({"success": False, "error": "缺少 user_id"}, ensure_ascii=False)

    if status == "active":
        result = await db.execute(
            select(ActivityState)
            .where(ActivityState.user_id == user_id)
            .where(ActivityState.activity_name == activity_name)
            .where(ActivityState.status == "active")
            .order_by(ActivityState.created_at.desc())
            .limit(1)
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.context = context or existing.context
            existing.updated_at = datetime.now()
            await db.commit()
            return json.dumps(
                {
                    "success": True,
                    "message": f"活动 '{activity_name}' 状态已更新",
                    "activity_id": existing.id,
                },
                ensure_ascii=False,
            )

        expire_hours = 24
        activity = ActivityState(
            user_id=user_id,
            activity_type=activity_type,
            activity_name=activity_name,
            status=status,
            context=context,
            expires_at=datetime.now() + timedelta(hours=expire_hours),
        )
        db.add(activity)
        await db.commit()

        return json.dumps(
            {
                "success": True,
                "message": f"活动 '{activity_name}' 已开始记录",
                "activity_id": activity.id,
            },
            ensure_ascii=False,
        )

    else:
        result = await db.execute(
            select(ActivityState)
            .where(ActivityState.user_id == user_id)
            .where(ActivityState.activity_name == activity_name)
            .where(ActivityState.status == "active")
            .order_by(ActivityState.created_at.desc())
            .limit(1)
        )
        activity = result.scalar_one_or_none()

        if activity:
            activity.status = status
            activity.context = context or activity.context
            activity.updated_at = datetime.now()
            await db.commit()

            return json.dumps(
                {
                    "success": True,
                    "message": f"活动 '{activity_name}' 状态已更新为 {status}",
                    "activity_id": activity.id,
                },
                ensure_ascii=False,
            )
        else:
            return json.dumps(
                {"success": False, "error": f"未找到活动 '{activity_name}'"},
                ensure_ascii=False,
            )


async def get_active_activities(db: AsyncSession, user_id: str) -> list[dict]:
    result = await db.execute(
        select(ActivityState)
        .where(ActivityState.user_id == user_id)
        .where(ActivityState.status == "active")
        .where(ActivityState.expires_at > datetime.now())
        .order_by(ActivityState.priority.desc(), ActivityState.created_at.desc())
    )
    activities = result.scalars().all()

    return [
        {
            "activity_type": a.activity_type,
            "activity_name": a.activity_name,
            "status": a.status,
            "context": a.context,
        }
        for a in activities
    ]


async def cleanup_expired_activities(db: AsyncSession) -> int:
    result = await db.execute(
        update(ActivityState)
        .where(ActivityState.status == "active")
        .where(ActivityState.expires_at < datetime.now())
        .values(status="expired")
    )
    await db.commit()
    return result.rowcount
