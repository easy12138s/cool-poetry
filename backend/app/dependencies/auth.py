from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User


async def verify_user(
    user_id: str,
    device_id: str,
    db: AsyncSession,
) -> User:
    """
    验证用户是否存在。

    Args:
        user_id: 用户ID
        device_id: 设备ID
        db: 数据库会话

    Returns:
        User: 用户对象

    Raises:
        HTTPException: 用户不存在时抛出 403 错误
    """
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "USER_NOT_REGISTERED",
                "message": "你还没有注册哦～请联系管理员添加用户信息",
                "suggestion": "如果你是新用户，请联系客服或管理员开通账号"
            }
        )

    # 验证设备是否匹配（可选，根据业务需求）
    if user.device_id and user.device_id != device_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "DEVICE_MISMATCH",
                "message": "设备信息不匹配",
                "suggestion": "请使用已绑定的设备进行访问"
            }
        )

    return user
