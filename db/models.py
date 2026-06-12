"""SQLAlchemy ORM 模型（与 Prisma Schema 保持同步）。

⚠️ 这些模型镜像 Prisma 管理的表结构，仅用于读写，禁止用它们创建/修改/迁移表。
ingest_tasks 由 data-pipeline 独占读写，但其 DDL 同样由 Prisma migration 管理。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class IngestTask(Base):
    __tablename__ = "ingest_tasks"

    task_id: Mapped[str] = mapped_column(Text, primary_key=True)
    document_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    completed_chunks: Mapped[int] = mapped_column(Integer, default=0)
    total_chunks: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'PROCESSING', 'SUCCESS', 'FAILED')",
            name="ingest_tasks_status_check",
        ),
        CheckConstraint("completed_chunks >= 0", name="ingest_tasks_completed_check"),
        CheckConstraint("total_chunks >= 0", name="ingest_tasks_total_check"),
        {"info": {"managed_by": "prisma_migration_do_not_create"}},
    )


# 占位：SourceDocument / KnowledgeChunk 的 ORM 映射在写库实现阶段补全，
# 同样必须镜像 prisma/schema.prisma，且不得自行迁移。
_ = String  # 保留 import，供后续模型使用
