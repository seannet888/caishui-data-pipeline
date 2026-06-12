"""POST /chunks/{chunk_id}/embed — trigger embedding for a human-verified chunk."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends

from api.dependencies import get_embedding_job_repository, get_embedder
from api.pipeline_trust import PipelinePrincipal, require_pipeline_principal
from embedding_job import EmbeddingJobRepository, embed_verified_chunk
from transformers.embedder import Embedder

router = APIRouter()


async def run_embedding_job(
    chunk_id: str,
    embedder: Embedder,
    repository: EmbeddingJobRepository,
) -> None:
    await embed_verified_chunk(chunk_id, embedder, repository)


@router.post("/chunks/{chunk_id}/embed", status_code=202)
async def embed_chunk(
    chunk_id: str,
    background_tasks: BackgroundTasks,
    _principal: PipelinePrincipal = Depends(require_pipeline_principal),
    embedder: Embedder = Depends(get_embedder),
    repository: EmbeddingJobRepository = Depends(get_embedding_job_repository),
):
    background_tasks.add_task(run_embedding_job, chunk_id, embedder, repository)
    return {"chunk_id": chunk_id, "status": "QUEUED"}
