"""Single verified chunk embedding job.

Used after webapp-side human verification. The job reuses the production
embedding lifecycle; it does not create a parallel vectorization path.
"""

from __future__ import annotations

from typing import Protocol

from output.embedding_lifecycle import (
    ChunkRepository,
    EmbedderProtocol,
    apply_embedding_lifecycle,
)


class EmbeddingJobRepository(ChunkRepository, Protocol):
    async def get_chunk_by_id(self, chunk_id: str): ...


async def embed_verified_chunk(
    chunk_id: str,
    embedder: EmbedderProtocol,
    repo: EmbeddingJobRepository,
) -> dict:
    chunk = await repo.get_chunk_by_id(chunk_id)
    if chunk is None:
        raise ValueError("chunk_not_found")
    if chunk.verification_status != "verified":
        raise ValueError("chunk_not_verified")
    if getattr(chunk, "retrieval_status", None) != "RETRIEVABLE":
        raise ValueError("chunk_not_retrievable")
    if getattr(chunk, "is_current_version", True) is not True:
        raise ValueError("chunk_not_current_version")

    await apply_embedding_lifecycle(chunk, embedder, repo)
    return {
        "chunk_id": chunk_id,
        "embedding_status": chunk.embedding_status,
    }
