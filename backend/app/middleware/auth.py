import json
import logging
from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware

from ..database import AsyncSessionLocal
from ..models import User

logger = logging.getLogger(__name__)


class UserAuthMiddleware(BaseHTTPMiddleware):
    """
    用户认证中间件。

    验证请求中的 user_id 和 device_id 是否有效。
    只对指定的路由进行验证（如 /api/v1/chat）。
    """

    def __init__(self, app, protected_paths: Optional[list] = None):
        super().__init__(app)
        # 需要保护的路由路径
        self.protected_paths = protected_paths or ["/api/v1/chat"]

    async def dispatch(self, request: Request, call_next):
        # 检查是否需要认证
        if not self._is_protected_path(request.url.path):
            return await call_next(request)

        # 只处理 POST 请求
        if request.method != "POST":
            return await call_next(request)

        try:
            # 解析请求体获取 user_id 和 device_id
            body = await request.body()
            if not body:
                return self._error_response(
                    "MISSING_PARAMS",
                    "请求参数不能为空",
                    "请提供 user_id 和 device_id"
                )

            data = json.loads(body)
            user_id = data.get("user_id")
            device_id = data.get("device_id")

            if not user_id or not device_id:
                return self._error_response(
                    "MISSING_PARAMS",
                    "缺少必要参数",
                    "请提供 user_id 和 device_id"
                )

            # 验证用户是否存在
            async with AsyncSessionLocal() as db:
                user = await self._verify_user(db, user_id, device_id)
                if not user:
                    return self._error_response(
                        "USER_NOT_REGISTERED",
                        "你还没有注册哦～",
                        "请联系管理员添加用户信息后再试"
                    )

                # 将用户信息存入请求状态，供后续使用
                request.state.user = user
                request.state.user_id = user_id
                request.state.device_id = device_id

            # 重新构造请求体（因为 body 只能读取一次）
            async def receive():
                return {"type": "http.request", "body": body}

            request = Request(request.scope, receive, request._send)

            # 继续处理请求
            response = await call_next(request)
            return response

        except json.JSONDecodeError:
            return self._error_response(
                "INVALID_JSON",
                "请求格式错误",
                "请确保请求体是有效的 JSON 格式"
            )
        except Exception as e:
            logger.error(f"Auth middleware error: {e}")
            return self._error_response(
                "INTERNAL_ERROR",
                "服务器内部错误",
                "请稍后重试"
            )

    def _is_protected_path(self, path: str) -> bool:
        """检查路径是否需要认证"""
        return any(path.startswith(protected) for protected in self.protected_paths)

    async def _verify_user(
        self,
        db: AsyncSession,
        user_id: str,
        device_id: str
    ) -> Optional[User]:
        """验证用户是否存在"""
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return None

        # 可选：验证设备匹配
        # if user.device_id and user.device_id != device_id:
        #     return None

        return user

    def _error_response(
        self,
        code: str,
        message: str,
        suggestion: str,
        status_code: int = 403
    ) -> JSONResponse:
        """构造错误响应"""
        return JSONResponse(
            status_code=status_code,
            content={
                "success": False,
                "error": {
                    "code": code,
                    "message": message,
                    "suggestion": suggestion
                }
            }
        )
