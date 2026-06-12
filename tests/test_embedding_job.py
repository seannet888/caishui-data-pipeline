from __future__ import annotations

import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest

from embedding_job import embed_verified_chunk


class RecordingRepository:
    def __init__(self, loaded) -> None:
        self.loaded = loaded
        self.saved = []

    async def get_chunk_by_id(self, chunk_id: str):
        return self.loaded if chunk_id == "chunk-1" else None

    async def save_chunk(self, chunk) -> None:
        self.saved.append(deepcopy(chunk))

    async def find_completed_embedding_in_document(self, document_id: str, identity: str):
        return None


class FixedEmbedder:
    model = "test-bge-large-zh-v1.5"
    dimension = 1024

    def __init__(self) -> None:
        self.calls = 0

    async def embed(self, content: str) -> list[float]:
        self.calls += 1
        return [0.5] * self.dimension


def chunk(**overrides):
    values = {
        "row_id": "chunk-1",
        "pipeline_chunk_id": "pipeline-chunk-1",
        "document_id": "doc-1",
        "content_hash": "h" * 64,
        "content": "第一条 企业发生符合条件的研发费用，可以加计扣除。",
        "verification_status": "verified",
        "verification_notes": "已核对官方原文",
        "retrieval_status": "RETRIEVABLE",
        "is_current_version": True,
        "embedding": None,
        "embedding_status": "PENDING",
        "embedding_error": None,
        "embedding_identity": None,
        "embedding_model": None,
        "embedding_dimension": None,
        "embedding_attempts": 0,
        "embedding_last_attempt_at": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_embedding_job_embeds_verified_retrievable_current_chunk():
    candidate = chunk()
    repo = RecordingRepository(candidate)
    embedder = FixedEmbedder()

    result = asyncio.run(embed_verified_chunk("chunk-1", embedder, repo))

    assert result == {
        "chunk_id": "chunk-1",
        "embedding_status": "COMPLETED",
    }
    assert embedder.calls == 1
    assert candidate.embedding_status == "COMPLETED"
    assert [saved.embedding_status for saved in repo.saved] == [
        "PROCESSING",
        "COMPLETED",
    ]


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"verification_status": "unverified"}, "chunk_not_verified"),
        ({"retrieval_status": "WITHDRAWN"}, "chunk_not_retrievable"),
        ({"is_current_version": False}, "chunk_not_current_version"),
    ],
)
def test_embedding_job_rejects_chunks_outside_production_retrieval(overrides, error):
    candidate = chunk(**overrides)
    repo = RecordingRepository(candidate)
    embedder = FixedEmbedder()

    with pytest.raises(ValueError, match=error):
        asyncio.run(embed_verified_chunk("chunk-1", embedder, repo))

    assert embedder.calls == 0
    assert repo.saved == []
