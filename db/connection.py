"""SQLAlchemy 异步引擎（与 Prisma 共享同一 PG 实例）。

⚠️ data-pipeline 不做任何 DDL 迁移：所有表结构由 Prisma migration 统一管理。
本模块只创建连接与 session，不调用 create_all。
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config.settings import get_settings

_settings = get_settings()

engine = create_async_engine(_settings.database_url, pool_size=10, max_overflow=5)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
