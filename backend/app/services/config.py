import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.config import SystemConfig

logger = logging.getLogger(__name__)


class ConfigManager:
    _instance: Optional["ConfigManager"] = None
    _cache: dict[str, tuple[Any, datetime, Optional[int]]] = {}
    _db_session: Optional[AsyncSession] = None
    _initialized: bool = False
    _refresh_task: Optional[asyncio.Task] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    async def initialize(cls, db: AsyncSession) -> None:
        if cls._instance._initialized:
            return

        cls._instance._db_session = db
        await cls._instance._load_cacheable_configs()
        cls._instance._initialized = True

        cls._instance._refresh_task = asyncio.create_task(cls._instance._refresh_loop())
        logger.info("ConfigManager initialized")

    @classmethod
    async def shutdown(cls) -> None:
        if cls._instance._refresh_task:
            cls._instance._refresh_task.cancel()
            try:
                await cls._instance._refresh_task
            except asyncio.CancelledError:
                pass
        cls._instance._initialized = False
        logger.info("ConfigManager shutdown")

    async def _load_cacheable_configs(self) -> None:
        if not self._db_session:
            return

        result = await self._db_session.execute(
            select(SystemConfig).where(
                SystemConfig.is_cacheable == True,
                SystemConfig.is_active == True,
            )
        )
        configs = result.scalars().all()

        for config in configs:
            value = self._parse_value(config.config_value, config.config_type)
            ttl = config.cache_ttl if config.cache_ttl > 0 else None
            self._cache[config.config_key] = (value, datetime.now(), ttl)

        logger.info(f"Loaded {len(configs)} cacheable configs")

    def _parse_value(self, value: str, config_type: str) -> Any:
        if config_type == "int":
            return int(value)
        elif config_type == "float":
            return float(value)
        elif config_type == "bool":
            return value.lower() in ("true", "1", "yes")
        elif config_type == "json":
            return json.loads(value)
        return value

    @classmethod
    def get(cls, key: str, default: Any = None, use_cache: bool = True) -> Any:
        instance = cls._instance
        if not instance:
            return default

        if use_cache and key in instance._cache:
            cached_value, cached_time, ttl = instance._cache[key]
            if ttl is None or datetime.now() - cached_time < timedelta(seconds=ttl):
                return cached_value

        return default

    @classmethod
    async def get_async(
        cls,
        key: str,
        default: Any = None,
        db: Optional[AsyncSession] = None,
    ) -> Any:
        instance = cls._instance
        session = db or (instance._db_session if instance else None)

        if not session:
            return default

        result = await session.execute(
            select(SystemConfig).where(
                SystemConfig.config_key == key,
                SystemConfig.is_active == True,
            )
        )
        config = result.scalar_one_or_none()

        if not config:
            return default

        value = instance._parse_value(config.config_value, config.config_type) if instance else default

        if instance and config.is_cacheable:
            ttl = config.cache_ttl if config.cache_ttl > 0 else None
            instance._cache[key] = (value, datetime.now(), ttl)

        return value

    @classmethod
    async def set(
        cls,
        key: str,
        value: Any,
        db: Optional[AsyncSession] = None,
    ) -> bool:
        instance = cls._instance
        session = db or (instance._db_session if instance else None)

        if not session:
            return False

        result = await session.execute(
            select(SystemConfig).where(SystemConfig.config_key == key)
        )
        config = result.scalar_one_or_none()

        if not config:
            return False

        if config.config_type == "json":
            config.config_value = json.dumps(value, ensure_ascii=False)
        else:
            config.config_value = str(value)

        await session.commit()

        if instance and config.is_cacheable:
            ttl = config.cache_ttl if config.cache_ttl > 0 else None
            instance._cache[key] = (value, datetime.now(), ttl)

        return True

    @classmethod
    async def refresh(cls, key: Optional[str] = None) -> None:
        instance = cls._instance
        if not instance:
            return

        if key:
            await instance._refresh_single(key)
        else:
            await instance._load_cacheable_configs()

    async def _refresh_single(self, key: str) -> None:
        if not self._db_session:
            return

        result = await self._db_session.execute(
            select(SystemConfig).where(
                SystemConfig.config_key == key,
                SystemConfig.is_active == True,
            )
        )
        config = result.scalar_one_or_none()

        if config and config.is_cacheable:
            value = self._parse_value(config.config_value, config.config_type)
            ttl = config.cache_ttl if config.cache_ttl > 0 else None
            self._cache[key] = (value, datetime.now(), ttl)

    async def _refresh_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(60)
                await self._refresh_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Config refresh failed: {e}")

    async def _refresh_expired(self) -> None:
        now = datetime.now()
        expired_keys = []

        for key, (_, cached_time, ttl) in self._cache.items():
            if ttl and (now - cached_time).total_seconds() >= ttl:
                expired_keys.append(key)

        for key in expired_keys:
            await self._refresh_single(key)


def get_config(key: str, default: Any = None) -> Any:
    return ConfigManager.get(key, default)


async def get_config_async(
    key: str,
    default: Any = None,
    db: Optional[AsyncSession] = None,
) -> Any:
    return await ConfigManager.get_async(key, default, db)


async def set_config(
    key: str,
    value: Any,
    db: Optional[AsyncSession] = None,
) -> bool:
    return await ConfigManager.set(key, value, db)
