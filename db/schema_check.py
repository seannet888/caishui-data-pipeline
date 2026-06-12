"""启动时 schema 一致性检查（见 ADR-0007）。

ingest_tasks 的 DDL 由 Prisma 拥有；这里把手写的 SQLAlchemy 镜像与真实表对比，
将“静默漂移”转化为“启动即失败”。仅做列名 + 可空性比对——类型跨 SQLAlchemy↔Postgres
映射歧义大，MVP 不强校验类型。
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from db.models import IngestTask


async def check_ingest_tasks_schema(engine: AsyncEngine) -> None:
    expected = {col.name: bool(col.nullable) for col in IngestTask.__table__.columns}

    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT column_name, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'ingest_tasks'
                """
            )
        )
        rows = result.all()

    if not rows:
        raise RuntimeError(
            "ingest_tasks 不存在——请先运行 Prisma 迁移（DDL 由 Prisma 拥有，见 ADR-0007）。"
        )

    actual = {name: (is_nullable == "YES") for name, is_nullable in rows}

    errors: list[str] = []
    missing = set(expected) - set(actual)
    if missing:
        errors.append(f"DB 缺少列: {sorted(missing)}")
    for name, nullable in expected.items():
        if name in actual and actual[name] != nullable:
            errors.append(
                f"列 '{name}' 可空性不一致: model={'NULL' if nullable else 'NOT NULL'}, "
                f"db={'NULL' if actual[name] else 'NOT NULL'}"
            )
    # DB 中多出的列（Prisma 领先于镜像）容忍，不报错。

    if errors:
        raise RuntimeError(
            "ingest_tasks schema 漂移（SQLAlchemy 镜像 vs Prisma 管理的真实表）: "
            + "; ".join(errors)
        )
