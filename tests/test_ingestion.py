from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

from ingestion import (
    IngestionDependencies,
    SourceDocumentInput,
    ingest_source_document,
    preview_source_document,
)


class RecordingChunkRepository:
    def __init__(self) -> None:
        self.saved = []

    async def save_chunk(self, chunk) -> None:
        if chunk.row_id is None:
            chunk.row_id = f"chunk-row-{len(self.saved) + 1}"
        self.saved.append(deepcopy(chunk))

    async def get_current_chunk(self, document_id: str, pipeline_chunk_id: str):
        return next(
            (
                deepcopy(chunk)
                for chunk in reversed(self.saved)
                if chunk.document_id == document_id
                and chunk.pipeline_chunk_id == pipeline_chunk_id
            ),
            None,
        )

    async def find_completed_embedding_in_document(
        self, document_id: str, identity: str
    ):
        return next(
            (
                chunk
                for chunk in reversed(self.saved)
                if chunk.document_id == document_id
                and chunk.embedding_identity == identity
                and chunk.embedding_status == "COMPLETED"
            ),
            None,
        )


class FixedEmbedder:
    model = "test-bge-large-zh-v1.5"
    dimension = 1024

    def __init__(self) -> None:
        self.calls = 0

    async def embed(self, content: str) -> list[float]:
        self.calls += 1
        return [0.25] * self.dimension


class FailingEmbedder(FixedEmbedder):
    async def embed(self, content: str) -> list[float]:
        self.calls += 1
        raise RuntimeError("embedding provider unavailable")


class RecordingLifecycle:
    def __init__(self) -> None:
        self.events: list[tuple] = []

    async def processing_started(self) -> None:
        self.events.append(("processing_started",))

    async def total_chunks_discovered(self, total: int) -> None:
        self.events.append(("total_chunks_discovered", total))

    async def source_metadata_discovered(self, metadata: dict) -> None:
        self.events.append(
            ("source_metadata_discovered", metadata.get("doc_number"))
        )

    async def chunk_persisted(self, completed: int, total: int) -> None:
        self.events.append(("chunk_persisted", completed, total))

    async def completed(self, result) -> None:
        self.events.append(("completed", result.status))

    async def failed(self, error_message: str) -> None:
        self.events.append(("failed", error_message))


def test_seed_markdown_source_becomes_verified_retrievable_chunks(
    tmp_path: Path,
):
    source_path = tmp_path / "研发费用政策.md"
    source_path.write_text(
        """# 关于研发费用加计扣除政策的通知

财税〔2023〕6号

第一条 企业开展研发活动中实际发生的研发费用，符合规定条件的，可以按照本通知规定在计算应纳税所得额时加计扣除。

第二条 本通知自2023年1月1日起施行，适用于符合条件的居民企业，并由主管税务机关依法办理。
""",
        encoding="utf-8",
    )
    repository = RecordingChunkRepository()

    result = asyncio.run(
        ingest_source_document(
            SourceDocumentInput(
                task_id="task-1",
                document_id="doc-1",
                file_path=str(source_path),
                file_name=source_path.name,
                file_hash="f" * 64,
                title="关于研发费用加计扣除政策的通知",
                source_channel="财政部官网",
                issuing_body="财政部、国家税务总局",
                jurisdiction="全国",
                doc_type="notice",
                effective_date=date(2023, 1, 1),
                source_section="正文",
                verification_method="seed",
                seed_batch_id="mvp-seed-1",
                verified_by="admin-1",
            ),
            IngestionDependencies(
                embedder=FixedEmbedder(),
                repository=repository,
            ),
        ),
    )

    assert result.status == "success"
    assert result.total_chunks == len(result.chunks) > 0

    final_rows = {
        chunk.pipeline_chunk_id: chunk for chunk in repository.saved
    }.values()
    assert len(list(final_rows)) == result.total_chunks
    assert all(chunk.verification_status == "verified" for chunk in final_rows)
    assert all(chunk.verification_method == "seed" for chunk in final_rows)
    assert all(chunk.embedding_status == "COMPLETED" for chunk in final_rows)
    assert all(len(chunk.embedding) == 1024 for chunk in final_rows)
    assert all(chunk.metadata["doc_number"] == "财税〔2023〕6号" for chunk in final_rows)


def test_reprocessing_identical_content_preserves_verified_embedding(
    tmp_path: Path,
):
    source_path = tmp_path / "研发费用政策.md"
    source_path.write_text(
        """财税〔2023〕6号

第一条 企业开展研发活动中实际发生的研发费用，符合规定条件的，可以按照规定在计算应纳税所得额时加计扣除。
""",
        encoding="utf-8",
    )
    repository = RecordingChunkRepository()
    embedder = FixedEmbedder()
    common = dict(
        document_id="doc-lifecycle",
        file_path=str(source_path),
        file_name=source_path.name,
        file_hash="9" * 64,
        title="研发费用政策",
        source_channel="财政部官网",
        issuing_body="财政部、国家税务总局",
        jurisdiction="全国",
        doc_type="notice",
        effective_date=date(2023, 1, 1),
        source_section="正文",
    )

    asyncio.run(
        ingest_source_document(
            SourceDocumentInput(
                task_id="task-seed",
                **common,
                verification_method="seed",
                seed_batch_id="mvp-seed-1",
                verified_by="admin-1",
            ),
            IngestionDependencies(embedder=embedder, repository=repository),
        )
    )
    first = deepcopy(repository.saved[-1])

    asyncio.run(
        ingest_source_document(
            SourceDocumentInput(task_id="task-rerun", **common),
            IngestionDependencies(embedder=embedder, repository=repository),
        )
    )
    current = repository.saved[-1]

    assert current.row_id == first.row_id
    assert current.verification_status == "verified"
    assert current.verification_method == "seed"
    assert current.embedding_status == "COMPLETED"
    assert current.embedding == first.embedding
    assert embedder.calls == 1


def test_preview_uses_same_chunk_identity_without_persistence_or_embedding(
    tmp_path: Path,
):
    source_path = tmp_path / "政策.md"
    source_path.write_text(
        """# 企业所得税政策

财税〔2024〕15号

第一条 企业发生符合条件的研发费用，可以依照现行规定在计算应纳税所得额时享受加计扣除政策。
""",
        encoding="utf-8",
    )
    source = SourceDocumentInput(
        task_id="preview-task",
        document_id="preview-doc",
        file_path=str(source_path),
        file_name=source_path.name,
        file_hash="e" * 64,
        title="企业所得税政策",
        source_channel="财政部官网",
        issuing_body="财政部、国家税务总局",
        jurisdiction="全国",
        doc_type="notice",
        effective_date=date(2024, 1, 1),
        source_section="正文",
    )

    first = preview_source_document(source)
    second = preview_source_document(source)

    assert len(first) == 1
    assert len(second) == 1
    assert first[0].embedding is None
    assert first[0].embedding_model is None
    assert first[0].metadata.doc_number == "财税〔2024〕15号"
    assert first[0].chunk_id == second[0].chunk_id
    assert first[0].content_hash == second[0].content_hash
    assert first[0].content == second[0].content
    assert first[0].metadata == second[0].metadata


def test_mvp_rejects_auto_verification_before_writing_or_embedding(
    tmp_path: Path,
):
    source_path = tmp_path / "政策.md"
    source_path.write_text(
        """财税〔2024〕15号

第一条 企业发生符合条件的研发费用，可以依照现行规定在计算应纳税所得额时享受加计扣除政策。
""",
        encoding="utf-8",
    )
    repository = RecordingChunkRepository()
    embedder = FixedEmbedder()

    with pytest.raises(ValueError, match="auto_verification_forbidden_in_mvp"):
        asyncio.run(
            ingest_source_document(
                SourceDocumentInput(
                    task_id="task-auto",
                    document_id="doc-auto",
                    file_path=str(source_path),
                    file_name=source_path.name,
                    file_hash="d" * 64,
                    title="企业所得税政策",
                    source_channel="财政部官网",
                    issuing_body="财政部、国家税务总局",
                    jurisdiction="全国",
                    doc_type="notice",
                    effective_date=date(2024, 1, 1),
                    source_section="正文",
                    verification_method="auto",
                ),
                IngestionDependencies(embedder=embedder, repository=repository),
            )
        )

    assert repository.saved == []


def test_embedding_failure_keeps_verification_and_returns_partial_failure(
    tmp_path: Path,
):
    source_path = tmp_path / "政策.md"
    source_path.write_text(
        """财税〔2024〕15号

第一条 企业发生符合条件的研发费用，可以依照现行规定在计算应纳税所得额时享受加计扣除政策。
""",
        encoding="utf-8",
    )
    repository = RecordingChunkRepository()

    result = asyncio.run(
        ingest_source_document(
            SourceDocumentInput(
                task_id="task-failed-embedding",
                document_id="doc-failed-embedding",
                file_path=str(source_path),
                file_name=source_path.name,
                file_hash="c" * 64,
                title="企业所得税政策",
                source_channel="财政部官网",
                issuing_body="财政部、国家税务总局",
                jurisdiction="全国",
                doc_type="notice",
                effective_date=date(2024, 1, 1),
                source_section="正文",
                verification_method="seed",
                seed_batch_id="mvp-seed-1",
                verified_by="admin-1",
            ),
            IngestionDependencies(
                embedder=FailingEmbedder(),
                repository=repository,
            ),
        )
    )

    final_row = repository.saved[-1]
    assert final_row.verification_status == "verified"
    assert final_row.embedding_status == "FAILED"
    assert final_row.embedding is None
    assert result.status == "partial_failure"
    assert result.errors == [
        f"{final_row.pipeline_chunk_id}:embedding provider unavailable"
    ]


def test_embedding_retry_limit_is_preserved_across_ingestion_tasks(
    tmp_path: Path,
):
    source_path = tmp_path / "重试政策.md"
    source_path.write_text(
        """财税〔2024〕15号

第一条 企业发生符合条件的研发费用，可以依照现行规定在计算应纳税所得额时享受加计扣除政策。
""",
        encoding="utf-8",
    )
    repository = RecordingChunkRepository()
    embedder = FailingEmbedder()

    for attempt in range(4):
        asyncio.run(
            ingest_source_document(
                SourceDocumentInput(
                    task_id=f"task-retry-{attempt}",
                    document_id="doc-retry",
                    file_path=str(source_path),
                    file_name=source_path.name,
                    file_hash="8" * 64,
                    title="重试政策",
                    source_channel="财政部官网",
                    issuing_body="财政部、国家税务总局",
                    jurisdiction="全国",
                    doc_type="notice",
                    effective_date=date(2024, 1, 1),
                    source_section="正文",
                    verification_method="seed",
                    seed_batch_id="mvp-seed-1",
                    verified_by="admin-1",
                ),
                IngestionDependencies(
                    embedder=embedder,
                    repository=repository,
                ),
            )
        )

    current = repository.saved[-1]
    assert embedder.calls == 3
    assert current.embedding_attempts == 3
    assert current.embedding_status == "FAILED"
    assert current.embedding_error == "automatic_retry_limit_reached"


def test_identical_rejected_chunk_cannot_be_seed_verified_by_reprocessing(
    tmp_path: Path,
):
    source_path = tmp_path / "已拒绝政策.md"
    source_path.write_text(
        """财税〔2024〕15号

第一条 企业发生符合条件的研发费用，可以依照现行规定在计算应纳税所得额时享受加计扣除政策。
""",
        encoding="utf-8",
    )
    repository = RecordingChunkRepository()
    embedder = FixedEmbedder()
    common = dict(
        document_id="doc-rejected",
        file_path=str(source_path),
        file_name=source_path.name,
        file_hash="7" * 64,
        title="已拒绝政策",
        source_channel="财政部官网",
        issuing_body="财政部、国家税务总局",
        jurisdiction="全国",
        doc_type="notice",
        effective_date=date(2024, 1, 1),
        source_section="正文",
    )

    asyncio.run(
        ingest_source_document(
            SourceDocumentInput(task_id="task-unverified", **common),
            IngestionDependencies(embedder=embedder, repository=repository),
        )
    )
    rejected = repository.saved[-1]
    rejected.verification_status = "rejected"
    rejected.verification_notes = "分块边界错误"

    asyncio.run(
        ingest_source_document(
            SourceDocumentInput(
                task_id="task-seed-retry",
                **common,
                verification_method="seed",
                seed_batch_id="mvp-seed-1",
                verified_by="admin-1",
            ),
            IngestionDependencies(embedder=embedder, repository=repository),
        )
    )

    current = repository.saved[-1]
    assert current.verification_status == "rejected"
    assert current.verification_notes == "分块边界错误"
    assert current.embedding is None
    assert embedder.calls == 0


def test_ingestion_reports_task_progress_through_lifecycle_adapter(
    tmp_path: Path,
):
    source_path = tmp_path / "政策.md"
    source_path.write_text(
        """财税〔2024〕15号

第一条 企业发生符合条件的研发费用，可以依照现行规定在计算应纳税所得额时享受加计扣除政策。
""",
        encoding="utf-8",
    )
    lifecycle = RecordingLifecycle()

    result = asyncio.run(
        ingest_source_document(
            SourceDocumentInput(
                task_id="task-progress",
                document_id="doc-progress",
                file_path=str(source_path),
                file_name=source_path.name,
                file_hash="b" * 64,
                title="企业所得税政策",
                source_channel="财政部官网",
                issuing_body="财政部、国家税务总局",
                jurisdiction="全国",
                doc_type="notice",
                effective_date=date(2024, 1, 1),
                source_section="正文",
                verification_method="seed",
                seed_batch_id="mvp-seed-1",
                verified_by="admin-1",
            ),
            IngestionDependencies(
                embedder=FixedEmbedder(),
                repository=RecordingChunkRepository(),
                lifecycle=lifecycle,
            ),
        )
    )

    assert lifecycle.events == [
        ("processing_started",),
        ("source_metadata_discovered", "财税〔2024〕15号"),
        ("total_chunks_discovered", result.total_chunks),
        ("chunk_persisted", 1, result.total_chunks),
        ("completed", "success"),
    ]
