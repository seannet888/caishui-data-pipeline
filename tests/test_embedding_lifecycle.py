from __future__ import annotations

import asyncio
from copy import deepcopy
from types import SimpleNamespace

from output.embedding_lifecycle import apply_embedding_lifecycle


class RecordingRepository:
    def __init__(self, existing=None) -> None:
        self.saved = []
        self.existing = existing

    async def save_chunk(self, chunk) -> None:
        self.saved.append(deepcopy(chunk))

    async def find_completed_embedding_in_document(
        self, document_id: str, identity: str
    ):
        return self.existing


class FixedEmbedder:
    model = "test-bge-large-zh-v1.5"
    dimension = 1024

    def __init__(self) -> None:
        self.calls = 0

    async def embed(self, content: str) -> list[float]:
        self.calls += 1
        return [0.5] * self.dimension


class FailingEmbedder(FixedEmbedder):
    async def embed(self, content: str) -> list[float]:
        self.calls += 1
        raise RuntimeError("embedding provider unavailable")


def chunk(**overrides):
    values = {
        "document_id": "doc-1",
        "content_hash": "h" * 64,
        "content": "第一条 企业发生符合条件的研发费用，可以加计扣除。",
        "verification_status": "verified",
        "verification_notes": None,
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


def test_unverified_chunk_is_saved_without_embedding():
    repo = RecordingRepository()
    embedder = FixedEmbedder()
    candidate = chunk(verification_status="unverified")

    asyncio.run(apply_embedding_lifecycle(candidate, embedder, repo))

    assert embedder.calls == 0
    assert candidate.embedding is None
    assert candidate.embedding_status == "PENDING"
    assert len(repo.saved) == 1


def test_verified_chunk_reuses_completed_embedding_with_same_identity():
    existing = SimpleNamespace(embedding=[0.25] * 1024)
    repo = RecordingRepository(existing=existing)
    embedder = FixedEmbedder()
    candidate = chunk()

    asyncio.run(apply_embedding_lifecycle(candidate, embedder, repo))

    assert embedder.calls == 0
    assert candidate.embedding == existing.embedding
    assert candidate.embedding_status == "COMPLETED"
    assert candidate.embedding_model == embedder.model
    assert candidate.embedding_dimension == embedder.dimension
    assert candidate.embedding_identity is not None
    assert len(repo.saved) == 1


def test_embedding_failure_records_failure_without_changing_verification():
    repo = RecordingRepository()
    embedder = FailingEmbedder()
    candidate = chunk()

    asyncio.run(apply_embedding_lifecycle(candidate, embedder, repo))

    assert candidate.verification_status == "verified"
    assert candidate.embedding is None
    assert candidate.embedding_status == "FAILED"
    assert candidate.embedding_error == "embedding provider unavailable"
    assert candidate.embedding_attempts == 1
    assert [saved.embedding_status for saved in repo.saved] == [
        "PROCESSING",
        "FAILED",
    ]
