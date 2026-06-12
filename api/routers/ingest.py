"""POST /ingest — 持久化上传文件并启动 Knowledge Chunk Ingestion。"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from api.dependencies import get_embedder
from api.pipeline_trust import PipelinePrincipal, require_pipeline_principal
from config.settings import get_settings
from db.connection import SessionLocal
from db.ingestion_adapter import PostgresIngestionAdapter, create_ingest_task
from ingestion import IngestionDependencies, SourceDocumentInput, ingest_source_document
from transformers.embedder import Embedder

router = APIRouter()


def _optional_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


async def run_ingest_pipeline(
    source: SourceDocumentInput,
    embedder: Embedder,
    actor_id: str,
) -> None:
    adapter = PostgresIngestionAdapter(
        session_factory=SessionLocal,
        task_id=source.task_id,
        document_id=source.document_id,
        source_file_path=source.file_path,
        actor_id=actor_id,
    )
    await ingest_source_document(
        source,
        IngestionDependencies(
            embedder=embedder,
            repository=adapter,
            lifecycle=adapter,
        ),
    )


@router.post("/ingest", status_code=202)
async def ingest(
    background_tasks: BackgroundTasks,
    principal: PipelinePrincipal = Depends(require_pipeline_principal),
    file: UploadFile = File(...),
    document_id: str = Form(...),
    file_hash: str = Form(...),
    title: str = Form(...),
    source_channel: str | None = Form(None),
    issuing_body: str | None = Form(None),
    jurisdiction: str | None = Form(None),
    doc_type: str | None = Form(None),
    effective_date: str | None = Form(None),
    expire_date: str | None = Form(None),
    verification_method: str | None = Form(None),
    seed_batch_id: str | None = Form(None),
    embedder: Embedder = Depends(get_embedder),
):
    if verification_method == "seed" and not principal.has_role("admin"):
        raise HTTPException(status_code=403, detail="seed_requires_admin")

    task_id = str(uuid.uuid4())
    content = await file.read()
    actual_hash = hashlib.sha256(content).hexdigest()
    if actual_hash != file_hash:
        raise HTTPException(status_code=400, detail="uploaded_file_hash_mismatch")

    storage_dir = Path(get_settings().storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "source.bin").suffix.lower()
    stored_path = storage_dir / f"{document_id}-{task_id}{suffix}"
    stored_path.write_bytes(content)

    await create_ingest_task(SessionLocal, task_id, document_id)
    source = SourceDocumentInput(
        task_id=task_id,
        document_id=document_id,
        file_path=str(stored_path),
        file_name=file.filename or stored_path.name,
        file_hash=file_hash,
        title=title,
        source_channel=source_channel,
        issuing_body=issuing_body,
        jurisdiction=jurisdiction,
        doc_type=doc_type,
        effective_date=_optional_date(effective_date),
        expire_date=_optional_date(expire_date),
        source_section="正文",
        verification_method=verification_method,
        seed_batch_id=seed_batch_id,
        verified_by=principal.actor_id if verification_method == "seed" else None,
    )
    background_tasks.add_task(
        run_ingest_pipeline, source, embedder, principal.actor_id
    )
    return {"task_id": task_id, "document_id": document_id, "status": "PENDING"}
