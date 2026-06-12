"""GET /status/{task_id} — 查询 Knowledge Chunk Ingestion 进度。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import IngestTaskRepository, get_ingest_task_repository
from api.pipeline_trust import PipelinePrincipal, require_pipeline_principal
from db.status_adapter import get_task_status

router = APIRouter()


@router.get("/status/{task_id}")
async def get_status(
    task_id: str,
    _principal: PipelinePrincipal = Depends(require_pipeline_principal),
    repository: IngestTaskRepository = Depends(get_ingest_task_repository),
):
    task = await get_task_status(repository, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task_not_found")
    return task
