"""启动时回收孤儿清洗任务（见 ADR-0008）。

MVP 用 FastAPI BackgroundTasks，单进程、无 Celery。进程重启会丢失所有在途任务，
其 ingest_tasks 行会停留在 PENDING/PROCESSING。由于是单进程，启动时任何非终态行
都必然是上一进程遗留的孤儿——无需时间阈值，直接标记 FAILED，并同步把对应
SourceDocument.processing_status 置为 FAILED，避免 /docs 页面永久显示"处理中"。

⚠️ 多副本部署会打破"启动即孤儿"的假设；MVP 不做多副本（见 ADR-0008）。
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

ORPHAN_ERROR = "orphaned task reclaimed after pipeline restart"


async def reclaim_orphaned_tasks(engine: AsyncEngine) -> int:
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                """
                UPDATE ingest_tasks
                SET status = 'FAILED',
                    error_message = :msg,
                    completed_at = NOW(),
                    updated_at = NOW()
                WHERE status IN ('PENDING', 'PROCESSING')
                RETURNING document_id
                """
            ),
            {"msg": ORPHAN_ERROR},
        )
        document_ids = [row[0] for row in result.all()]

        if document_ids:
            await conn.execute(
                text(
                    """
                    UPDATE source_documents
                    SET processing_status = 'FAILED',
                        error_message = :msg,
                        updated_at = NOW()
                    WHERE id = ANY(:ids)
                      AND processing_status IN ('PENDING', 'PROCESSING')
                    """
                ),
                {"msg": ORPHAN_ERROR, "ids": document_ids},
            )

    return len(document_ids)
