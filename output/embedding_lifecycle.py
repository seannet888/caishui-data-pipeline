"""生产 embedding 生命周期规则。

该模块只负责 Knowledge Chunk 是否生成、复用、重试和记录 embedding 状态。
Writer 只负责调用该规则并保存结果，避免把信任规则和写库 Adapter 混在一起。
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Protocol

MAX_EMBEDDING_ATTEMPTS = 3


class ChunkRepository(Protocol):
    async def save_chunk(self, chunk) -> None: ...

    async def find_completed_embedding_in_document(
        self, document_id: str, identity: str
    ): ...


class EmbedderProtocol(Protocol):
    model: str
    dimension: int

    async def embed(self, content: str) -> list[float]: ...


def embedding_identity(chunk, embedder: EmbedderProtocol) -> str:
    raw = f"{chunk.document_id}:{chunk.content_hash}:{embedder.model}:{embedder.dimension}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def apply_embedding_lifecycle(
    chunk,
    embedder: EmbedderProtocol,
    repo: ChunkRepository,
) -> None:
    # 非 verified：禁止生成生产向量；rejected 必须保留拒绝原因。
    if chunk.verification_status != "verified":
        chunk.embedding = None
        chunk.embedding_status = "PENDING"
        if chunk.verification_status == "rejected":
            assert chunk.verification_notes, "rejected chunk must record verification_notes"
        await repo.save_chunk(chunk)
        return

    identity = embedding_identity(chunk, embedder)

    existing = await repo.find_completed_embedding_in_document(
        document_id=chunk.document_id, identity=identity
    )
    if existing:
        chunk.embedding_identity = identity
        chunk.embedding = existing.embedding
        chunk.embedding_model = embedder.model
        chunk.embedding_dimension = embedder.dimension
        chunk.embedding_status = "COMPLETED"
        await repo.save_chunk(chunk)
        return

    if chunk.embedding_attempts >= MAX_EMBEDDING_ATTEMPTS:
        chunk.embedding_status = "FAILED"
        chunk.embedding_error = "automatic_retry_limit_reached"
        await repo.save_chunk(chunk)
        return

    chunk.embedding_identity = identity
    chunk.embedding_model = embedder.model
    chunk.embedding_dimension = embedder.dimension
    chunk.embedding_status = "PROCESSING"
    chunk.embedding_attempts += 1
    chunk.embedding_last_attempt_at = datetime.now(UTC)
    await repo.save_chunk(chunk)

    try:
        chunk.embedding = await embedder.embed(chunk.content)
        chunk.embedding_status = "COMPLETED"
        chunk.embedding_error = None
    except Exception as exc:  # noqa: BLE001 - 记录后人工/后台重试
        chunk.embedding = None
        chunk.embedding_status = "FAILED"
        chunk.embedding_error = str(exc)

    await repo.save_chunk(chunk)
