"""FastAPI 依赖注入（DB session、Embedder 单例）。"""

from __future__ import annotations

from functools import lru_cache

from db.connection import SessionLocal
from db.ingestion_adapter import get_ingest_task
from transformers.embedder import Embedder


@lru_cache
def get_embedder() -> Embedder:
    return Embedder()


class IngestTaskRepository:
    async def get_ingest_task(self, task_id: str):
        return await get_ingest_task(SessionLocal, task_id)


def get_ingest_task_repository() -> IngestTaskRepository:
    return IngestTaskRepository()
