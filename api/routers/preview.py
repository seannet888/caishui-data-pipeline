"""POST /preview — 使用正式 Ingestion Implementation 预览，不验证、不向量化、不入库。"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile

from api.pipeline_trust import PipelinePrincipal, require_pipeline_principal
from ingestion import SourceDocumentInput
from output.preview_adapter import build_preview_output
from output.schemas import PipelineOutput

router = APIRouter()


@router.post("/preview")
async def preview(
    _principal: PipelinePrincipal = Depends(require_pipeline_principal),
    file: UploadFile = File(...),
    title: str | None = Form(None),
    source_channel: str | None = Form(None),
    issuing_body: str | None = Form(None),
    jurisdiction: str | None = Form(None),
    doc_type: str | None = Form(None),
) -> PipelineOutput:
    content = await file.read()
    suffix = Path(file.filename or "source.md").suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
        temp.write(content)
        temp_path = Path(temp.name)

    try:
        return build_preview_output(
            SourceDocumentInput(
                task_id="preview",
                document_id="preview",
                file_path=str(temp_path),
                file_name=file.filename or temp_path.name,
                file_hash=hashlib.sha256(content).hexdigest(),
                title=title or Path(file.filename or "未命名").stem,
                source_channel=source_channel,
                issuing_body=issuing_body,
                jurisdiction=jurisdiction,
                doc_type=doc_type,
                source_section="正文",
            )
        )
    finally:
        temp_path.unlink(missing_ok=True)
