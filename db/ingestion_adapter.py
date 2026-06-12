"""PostgreSQL Adapter for Knowledge Chunk Ingestion.

所有 DDL 由 Prisma migration 管理；本 Adapter 只执行参数化 DML。
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ingestion import IngestionChunk
from output.schemas import PipelineOutput


def _row_id() -> str:
    return f"c{uuid.uuid4().hex}"


def _vector_literal(vector: list[float] | None) -> str | None:
    return None if vector is None else f"[{','.join(str(value) for value in vector)}]"


def _parse_vector(value: str | None) -> list[float] | None:
    if value is None:
        return None
    return [float(item) for item in value.strip("[]").split(",") if item]


def _enum(value: str | None) -> str | None:
    return value.upper() if value else None


def _chunk_from_row(row) -> IngestionChunk:
    chunk = IngestionChunk(
        pipeline_chunk_id=row["pipeline_chunk_id"],
        document_id=row["document_id"],
        chunk_index=row["chunk_index"],
        chunk_type=row["chunk_type"],
        content=row["content"],
        content_hash=row["content_hash"],
        metadata=dict(row["metadata"]),
        row_id=row["id"],
        verification_status=row["verification_status"],
        verification_method=row["verification_method"],
        verified_by=row["verified_by"],
        verified_at=row["verified_at"],
        verification_notes=row["verification_notes"],
        embedding=_parse_vector(row["embedding"]),
        embedding_status=row["embedding_status"],
        embedding_error=row["embedding_error"],
        embedding_identity=row["embedding_identity"],
        embedding_model=row["embedding_model"],
        embedding_dimension=row["embedding_dimension"],
        embedding_attempts=row["embedding_attempts"],
        embedding_last_attempt_at=row["embedding_last_attempt_at"],
    )
    if "retrieval_status" in row:
        chunk.retrieval_status = row["retrieval_status"]
    if "is_current_version" in row:
        chunk.is_current_version = row["is_current_version"]
    return chunk


@dataclass
class PostgresIngestionAdapter:
    session_factory: async_sessionmaker[AsyncSession]
    task_id: str
    document_id: str
    source_file_path: str | None = None
    actor_id: str = "system"

    async def get_chunk_by_id(self, chunk_id: str) -> IngestionChunk | None:
        async with self.session_factory() as session:
            row = (
                await session.execute(
                    text(
                        """
                        SELECT id, pipeline_chunk_id, document_id, chunk_index,
                               chunk_type, content, content_hash, metadata,
                               verification_status, verification_method,
                               verified_by, verified_at, verification_notes,
                               embedding::text AS embedding, embedding_status,
                               embedding_error, embedding_identity,
                               embedding_model, embedding_dimension,
                               embedding_attempts, embedding_last_attempt_at,
                               retrieval_status, is_current_version
                        FROM knowledge_chunks
                        WHERE id = :chunk_id
                        LIMIT 1
                        """
                    ),
                    {"chunk_id": chunk_id},
                )
            ).mappings().first()
        return _chunk_from_row(row) if row else None

    async def get_current_chunk(
        self, document_id: str, pipeline_chunk_id: str
    ) -> IngestionChunk | None:
        async with self.session_factory() as session:
            row = (
                await session.execute(
                    text(
                        """
                        SELECT id, pipeline_chunk_id, document_id, chunk_index,
                               chunk_type, content, content_hash, metadata,
                               verification_status, verification_method,
                               verified_by, verified_at, verification_notes,
                               embedding::text AS embedding, embedding_status,
                               embedding_error, embedding_identity,
                               embedding_model, embedding_dimension,
                               embedding_attempts, embedding_last_attempt_at
                        FROM knowledge_chunks
                        WHERE document_id = :document_id
                          AND pipeline_chunk_id = :pipeline_chunk_id
                          AND is_current_version = true
                        ORDER BY created_at DESC
                        LIMIT 1
                        """
                    ),
                    {
                        "document_id": document_id,
                        "pipeline_chunk_id": pipeline_chunk_id,
                    },
                )
            ).mappings().first()
        return _chunk_from_row(row) if row else None

    async def save_chunk(self, chunk: IngestionChunk) -> None:
        async with self.session_factory() as session, session.begin():
            if not getattr(chunk, "row_id", None):
                await session.execute(
                    text(
                        """
                        SELECT pg_advisory_xact_lock(
                            hashtextextended(:location_key, 0)
                        )
                        """
                    ),
                    {
                        "location_key": (
                            f"{chunk.document_id}:{chunk.pipeline_chunk_id}"
                        )
                    },
                )
                current = (
                    await session.execute(
                        text(
                            """
                            SELECT id, content_hash
                            FROM knowledge_chunks
                            WHERE document_id = :document_id
                              AND pipeline_chunk_id = :pipeline_chunk_id
                              AND is_current_version = true
                            ORDER BY created_at DESC
                            LIMIT 1
                            """
                        ),
                        {
                            "document_id": chunk.document_id,
                            "pipeline_chunk_id": chunk.pipeline_chunk_id,
                        },
                    )
                ).mappings().first()
                if current and current["content_hash"] == chunk.content_hash:
                    chunk.row_id = current["id"]
                else:
                    if current:
                        await session.execute(
                            text(
                                """
                                UPDATE knowledge_chunks
                                SET is_current_version = false, updated_at = NOW()
                                WHERE id = :id
                                """
                            ),
                            {"id": current["id"]},
                        )
                    chunk.row_id = _row_id()
                    await self._insert_chunk(session, chunk)
                    return

            await self._update_chunk(session, chunk)

    async def _insert_chunk(
        self, session: AsyncSession, chunk: IngestionChunk
    ) -> None:
        metadata = chunk.metadata
        await session.execute(
            text(
                """
                INSERT INTO knowledge_chunks (
                    id, pipeline_chunk_id, document_id, content, content_hash,
                    chunk_index, chunk_type, embedding, embedding_status,
                    embedding_error, embedding_identity, embedding_model,
                    embedding_dimension, embedding_attempts,
                    embedding_last_attempt_at, publish_date, effective_date,
                    expire_date, jurisdiction, source_channel, doc_type,
                    authority_rank, is_current_version, verification_status,
                    verification_method, verified_by, verified_at,
                    verification_notes, provision_type, retrieval_status,
                    metadata, created_at, updated_at
                ) VALUES (
                    :id, :pipeline_chunk_id, :document_id, :content, :content_hash,
                    :chunk_index, :chunk_type, CAST(:embedding AS vector),
                    CAST(:embedding_status AS "EmbeddingStatus"),
                    :embedding_error, :embedding_identity, :embedding_model,
                    :embedding_dimension, :embedding_attempts,
                    :embedding_last_attempt_at, :publish_date, :effective_date,
                    :expire_date, :jurisdiction, :source_channel,
                    CAST(:doc_type AS "DocType"), :authority_rank, true,
                    :verification_status, :verification_method, :verified_by,
                    :verified_at, :verification_notes, 'operative',
                    CAST('RETRIEVABLE' AS "RetrievalStatus"),
                    CAST(:metadata AS jsonb), :created_at, :updated_at
                )
                """
            ),
            self._params(chunk),
        )

    async def _update_chunk(
        self, session: AsyncSession, chunk: IngestionChunk
    ) -> None:
        await session.execute(
            text(
                """
                UPDATE knowledge_chunks
                SET embedding = CAST(:embedding AS vector),
                    embedding_status = CAST(:embedding_status AS "EmbeddingStatus"),
                    embedding_error = :embedding_error,
                    embedding_identity = :embedding_identity,
                    embedding_model = :embedding_model,
                    embedding_dimension = :embedding_dimension,
                    embedding_attempts = :embedding_attempts,
                    embedding_last_attempt_at = :embedding_last_attempt_at,
                    verification_status = :verification_status,
                    verification_method = :verification_method,
                    verified_by = :verified_by,
                    verified_at = :verified_at,
                    verification_notes = :verification_notes,
                    metadata = CAST(:metadata AS jsonb),
                    updated_at = :updated_at
                WHERE id = :id
                """
            ),
            self._params(chunk),
        )

    def _params(self, chunk: IngestionChunk) -> dict:
        now = datetime.now(UTC)
        metadata = chunk.metadata
        return {
            "id": chunk.row_id,
            "pipeline_chunk_id": chunk.pipeline_chunk_id,
            "document_id": chunk.document_id,
            "content": chunk.content,
            "content_hash": chunk.content_hash,
            "chunk_index": chunk.chunk_index,
            "chunk_type": chunk.chunk_type,
            "embedding": _vector_literal(chunk.embedding),
            "embedding_status": chunk.embedding_status,
            "embedding_error": chunk.embedding_error,
            "embedding_identity": chunk.embedding_identity,
            "embedding_model": chunk.embedding_model,
            "embedding_dimension": chunk.embedding_dimension,
            "embedding_attempts": chunk.embedding_attempts,
            "embedding_last_attempt_at": chunk.embedding_last_attempt_at,
            "publish_date": metadata.get("publish_date"),
            "effective_date": metadata.get("effective_date"),
            "expire_date": metadata.get("expire_date"),
            "jurisdiction": metadata.get("jurisdiction"),
            "source_channel": metadata.get("source_channel"),
            "doc_type": _enum(metadata.get("doc_type")),
            "authority_rank": metadata.get("authority_rank"),
            "verification_status": chunk.verification_status,
            "verification_method": chunk.verification_method,
            "verified_by": chunk.verified_by,
            "verified_at": chunk.verified_at,
            "verification_notes": chunk.verification_notes,
            "metadata": json.dumps(metadata, default=str, ensure_ascii=False),
            "created_at": now,
            "updated_at": now,
        }

    async def find_completed_embedding_in_document(
        self, document_id: str, identity: str
    ):
        async with self.session_factory() as session:
            row = (
                await session.execute(
                    text(
                        """
                        SELECT embedding::text AS embedding
                        FROM knowledge_chunks
                        WHERE document_id = :document_id
                          AND embedding_identity = :identity
                          AND embedding_status = CAST('COMPLETED' AS "EmbeddingStatus")
                          AND embedding IS NOT NULL
                        LIMIT 1
                        """
                    ),
                    {"document_id": document_id, "identity": identity},
                )
            ).mappings().first()
        if not row:
            return None
        return SimpleNamespace(embedding=_parse_vector(row["embedding"]))

    async def processing_started(self) -> None:
        await self._update_task_and_document(
            task_status="PROCESSING", document_status="PROCESSING", started=True
        )

    async def total_chunks_discovered(self, total: int) -> None:
        await self._update_task(total_chunks=total)

    async def source_metadata_discovered(self, metadata: dict) -> None:
        async with self.session_factory() as session, session.begin():
            await session.execute(
                text(
                    """
                    UPDATE source_documents
                    SET doc_number = :doc_number,
                        publish_date = :publish_date,
                        effective_date = COALESCE(:effective_date, effective_date),
                        expire_date = COALESCE(:expire_date, expire_date),
                        jurisdiction = COALESCE(:jurisdiction, jurisdiction),
                        issuing_body = COALESCE(:issuing_body, issuing_body),
                        source_channel = COALESCE(:source_channel, source_channel),
                        doc_type = COALESCE(
                            CAST(:doc_type AS "DocType"),
                            doc_type
                        ),
                        authority_rank = :authority_rank,
                        file_path = COALESCE(:file_path, file_path),
                        updated_at = NOW()
                    WHERE id = :document_id
                    """
                ),
                {
                    "document_id": self.document_id,
                    "doc_number": metadata.get("doc_number"),
                    "publish_date": metadata.get("publish_date"),
                    "effective_date": metadata.get("effective_date"),
                    "expire_date": metadata.get("expire_date"),
                    "jurisdiction": metadata.get("jurisdiction"),
                    "issuing_body": metadata.get("issuing_body"),
                    "source_channel": metadata.get("source_channel"),
                    "doc_type": _enum(metadata.get("doc_type")),
                    "authority_rank": metadata.get("authority_rank"),
                    "file_path": self.source_file_path,
                },
            )
    async def chunk_persisted(self, completed: int, total: int) -> None:
        await self._update_task(completed_chunks=completed, total_chunks=total)

    async def completed(self, result: PipelineOutput) -> None:
        error_message = "; ".join(result.errors) or None
        await self._update_task_and_document(
            task_status="SUCCESS",
            document_status="COMPLETED",
            completed=True,
            error_message=error_message,
        )

    async def failed(self, error_message: str) -> None:
        await self._update_task_and_document(
            task_status="FAILED",
            document_status="FAILED",
            completed=True,
            error_message=error_message,
        )

    async def _update_task(self, **values) -> None:
        assignments = ", ".join(f"{name} = :{name}" for name in values)
        async with self.session_factory() as session, session.begin():
            await session.execute(
                text(
                    f"""
                    UPDATE ingest_tasks
                    SET {assignments}, updated_at = NOW()
                    WHERE task_id = :task_id
                    """
                ),
                {"task_id": self.task_id, **values},
            )

    async def _update_task_and_document(
        self,
        *,
        task_status: str,
        document_status: str,
        started: bool = False,
        completed: bool = False,
        error_message: str | None = None,
    ) -> None:
        async with self.session_factory() as session, session.begin():
            await session.execute(
                text(
                    """
                    UPDATE ingest_tasks
                    SET status = :task_status,
                        started_at = CASE WHEN :started THEN NOW() ELSE started_at END,
                        completed_at = CASE WHEN :completed THEN NOW() ELSE completed_at END,
                        error_message = :error_message,
                        updated_at = NOW()
                    WHERE task_id = :task_id
                    """
                ),
                {
                    "task_id": self.task_id,
                    "task_status": task_status,
                    "started": started,
                    "completed": completed,
                    "error_message": error_message,
                },
            )
            action = (
                "ingest_started"
                if task_status == "PROCESSING"
                else "ingest_completed"
                if task_status == "SUCCESS"
                else "ingest_failed"
            )
            await session.execute(
                text(
                    """
                    INSERT INTO audit_events (
                        id, actor_id, action, target_type, target_id,
                        reason, payload, created_at
                    ) VALUES (
                        :id, :actor_id, :action, 'SourceDocument', :target_id,
                        :reason, CAST(:payload AS jsonb), NOW()
                    )
                    """
                ),
                {
                    "id": _row_id(),
                    "actor_id": self.actor_id,
                    "action": action,
                    "target_id": self.document_id,
                    "reason": error_message,
                    "payload": json.dumps(
                        {"task_id": self.task_id, "task_status": task_status}
                    ),
                },
            )
            await session.execute(
                text(
                    """
                    UPDATE source_documents
                    SET processing_status = CAST(:document_status AS "ProcessingStatus"),
                        error_message = :error_message,
                        processed_at = CASE WHEN :completed THEN NOW() ELSE processed_at END,
                        updated_at = NOW()
                    WHERE id = :document_id
                    """
                ),
                {
                    "document_id": self.document_id,
                    "document_status": document_status,
                    "completed": completed,
                    "error_message": error_message,
                },
            )


async def create_ingest_task(
    session_factory: async_sessionmaker[AsyncSession],
    task_id: str,
    document_id: str,
) -> None:
    async with session_factory() as session, session.begin():
        await session.execute(
            text(
                """
                INSERT INTO ingest_tasks (
                    task_id, document_id, status, completed_chunks, total_chunks,
                    created_at, updated_at
                ) VALUES (
                    :task_id, :document_id, 'PENDING', 0, 0, NOW(), NOW()
                )
                """
            ),
            {"task_id": task_id, "document_id": document_id},
        )


async def get_ingest_task(
    session_factory: async_sessionmaker[AsyncSession], task_id: str
) -> dict | None:
    async with session_factory() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT task_id, document_id, status, completed_chunks,
                           total_chunks, error_message, created_at, started_at,
                           completed_at, updated_at
                    FROM ingest_tasks
                    WHERE task_id = :task_id
                    """
                ),
                {"task_id": task_id},
            )
        ).mappings().first()
    return dict(row) if row else None
