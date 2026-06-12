"""Knowledge Chunk Ingestion Module.

对外只暴露 Source Document 输入与 Pipeline Output；内部工作对象承载验证和
Embedding 生命周期，不污染跨引擎 ChunkOutput 契约。
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Protocol

from chunk_lifecycle import reconcile_chunk
from loaders.base_loader import BaseLoader
from loaders.excel_loader import ExcelLoader
from loaders.md_loader import MdLoader
from loaders.pdf_loader import PdfLoader
from output.schemas import ChunkOutput, DocType, PipelineOutput, TaxMetadata
from output.writer import EmbedderProtocol, mark_seed_verified, persist_chunk
from transformers.chunker import chunk_markdown
from transformers.metadata_enricher import (
    detect_has_formula,
    detect_has_table,
    extract_doc_number,
    extract_publish_date,
    infer_authority_rank,
)


class IngestionChunkRepository(Protocol):
    async def get_current_chunk(
        self, document_id: str, pipeline_chunk_id: str
    ): ...

    async def save_chunk(self, chunk) -> None: ...

    async def find_completed_embedding_in_document(
        self, document_id: str, identity: str
    ): ...


class IngestionLifecycle(Protocol):
    async def processing_started(self) -> None: ...

    async def total_chunks_discovered(self, total: int) -> None: ...

    async def source_metadata_discovered(self, metadata: dict) -> None: ...

    async def chunk_persisted(self, completed: int, total: int) -> None: ...

    async def completed(self, result: PipelineOutput) -> None: ...

    async def failed(self, error_message: str) -> None: ...


@dataclass(frozen=True)
class IngestionDependencies:
    embedder: EmbedderProtocol
    repository: IngestionChunkRepository
    lifecycle: IngestionLifecycle | None = None


@dataclass(frozen=True)
class SourceDocumentInput:
    task_id: str
    document_id: str
    file_path: str
    file_name: str
    file_hash: str
    title: str
    source_channel: str | None = None
    issuing_body: str | None = None
    jurisdiction: str | None = None
    doc_type: str | None = None
    effective_date: date | None = None
    expire_date: date | None = None
    source_section: str | None = None
    verification_method: str | None = None
    seed_batch_id: str | None = None
    verified_by: str | None = None


@dataclass
class IngestionChunk:
    pipeline_chunk_id: str
    document_id: str
    chunk_index: int
    chunk_type: str
    content: str
    content_hash: str
    metadata: dict
    row_id: str | None = None
    verification_status: str = "unverified"
    verification_method: str | None = None
    verified_by: str | None = None
    verified_at: datetime | None = None
    verification_notes: str | None = None
    embedding: list[float] | None = None
    embedding_status: str = "PENDING"
    embedding_error: str | None = None
    embedding_identity: str | None = None
    embedding_model: str | None = None
    embedding_dimension: int | None = None
    embedding_attempts: int = 0
    embedding_last_attempt_at: datetime | None = None


_LOADERS: dict[str, type[BaseLoader]] = {
    ".pdf": PdfLoader,
    ".md": MdLoader,
    ".markdown": MdLoader,
    ".xlsx": ExcelLoader,
    ".csv": ExcelLoader,
}


def _select_loader(file_path: str) -> BaseLoader:
    suffix = Path(file_path).suffix.lower()
    loader = _LOADERS.get(suffix)
    if loader is None:
        raise ValueError(f"unsupported_file_type:{suffix.lstrip('.')}")
    return loader()


def _stable_location_id(file_hash: str, chunk_index: int) -> str:
    return hashlib.sha256(f"{file_hash}{chunk_index}".encode()).hexdigest()


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def _metadata_for_source(source: SourceDocumentInput, markdown: str, page_metadata: dict) -> dict:
    doc_number = extract_doc_number(markdown)
    metadata = {
        "title": source.title,
        "doc_number": doc_number,
        "publish_date": extract_publish_date(markdown, page_metadata),
        "effective_date": source.effective_date,
        "expire_date": source.expire_date,
        "jurisdiction": source.jurisdiction,
        "issuing_body": source.issuing_body,
        "source_channel": source.source_channel,
        "source_section": source.source_section,
        "doc_type": source.doc_type,
    }
    metadata["authority_rank"] = infer_authority_rank(metadata)
    return metadata


def _to_output(chunk: IngestionChunk) -> ChunkOutput:
    metadata = TaxMetadata(
        **{
            **chunk.metadata,
            "has_table": detect_has_table(chunk.content),
            "has_formula": detect_has_formula(chunk.content),
        }
    )
    return ChunkOutput(
        chunk_id=chunk.pipeline_chunk_id,
        document_id=chunk.document_id,
        chunk_index=chunk.chunk_index,
        chunk_type=chunk.chunk_type,
        content=chunk.content,
        content_hash=chunk.content_hash,
        embedding=chunk.embedding,
        embedding_model=chunk.embedding_model,
        metadata=metadata,
    )


async def ingest_source_document(
    source: SourceDocumentInput,
    dependencies: IngestionDependencies,
) -> PipelineOutput:
    started = time.perf_counter()
    lifecycle = dependencies.lifecycle
    try:
        if lifecycle:
            await lifecycle.processing_started()
        if source.verification_method == "auto":
            raise ValueError("auto_verification_forbidden_in_mvp")
        working_chunks = _prepare_chunks(source)
        if lifecycle:
            await lifecycle.source_metadata_discovered(
                working_chunks[0].metadata if working_chunks else {}
            )
            await lifecycle.total_chunks_discovered(len(working_chunks))

        for completed, chunk in enumerate(working_chunks, start=1):
            current = await dependencies.repository.get_current_chunk(
                chunk.document_id, chunk.pipeline_chunk_id
            )
            lifecycle_decision = reconcile_chunk(chunk, current)
            if source.verification_method == "seed":
                if not source.seed_batch_id or not source.verified_by:
                    raise ValueError("seed_verification_requires_batch_and_actor")
                if (
                    lifecycle_decision.action != "preserve_current"
                    or chunk.verification_status == "unverified"
                ):
                    mark_seed_verified(
                        chunk,
                        seed_batch_id=source.seed_batch_id,
                        imported_by=source.verified_by,
                    )
            await persist_chunk(
                chunk,
                embedder=dependencies.embedder,
                repo=dependencies.repository,
            )
            if lifecycle:
                await lifecycle.chunk_persisted(completed, len(working_chunks))

        outputs = [_to_output(chunk) for chunk in working_chunks]
        errors = [
            f"{chunk.pipeline_chunk_id}:{chunk.embedding_error}"
            for chunk in working_chunks
            if chunk.embedding_status == "FAILED" and chunk.embedding_error
        ]
        result = PipelineOutput(
            task_id=source.task_id,
            document_id=source.document_id,
            status="partial_failure" if errors else "success",
            chunks=outputs,
            total_chunks=len(outputs),
            processing_time_ms=int((time.perf_counter() - started) * 1000),
            errors=errors,
        )
        if lifecycle:
            await lifecycle.completed(result)
        return result
    except Exception as exc:
        if lifecycle:
            await lifecycle.failed(str(exc))
        raise


def preview_source_document(source: SourceDocumentInput) -> list[ChunkOutput]:
    """运行与正式入库相同的解析/分块/元数据 Implementation，但不验证、向量化或写库。"""
    return [_to_output(chunk) for chunk in _prepare_chunks(source)]


def _prepare_chunks(source: SourceDocumentInput) -> list[IngestionChunk]:
    loaded = _select_loader(source.file_path).load(source.file_path)
    source_metadata = _metadata_for_source(
        source, loaded.markdown, loaded.page_metadata
    )
    working_chunks: list[IngestionChunk] = []

    for raw_chunk in chunk_markdown(loaded.markdown):
        chunk = IngestionChunk(
            pipeline_chunk_id=_stable_location_id(
                source.file_hash, raw_chunk.chunk_index
            ),
            document_id=source.document_id,
            chunk_index=raw_chunk.chunk_index,
            chunk_type=raw_chunk.chunk_type,
            content=raw_chunk.content,
            content_hash=_content_hash(raw_chunk.content),
            metadata={**source_metadata},
        )
        working_chunks.append(chunk)
    return working_chunks
