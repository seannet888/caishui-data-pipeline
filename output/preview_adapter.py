"""Preview Output Adapter.

Preview uses the same parsing/chunking/metadata implementation as ingestion,
but it must not verify, embed, or persist chunks.
"""

from __future__ import annotations

import time

from ingestion import SourceDocumentInput, preview_source_document
from output.schemas import PipelineOutput


def build_preview_output(source: SourceDocumentInput) -> PipelineOutput:
    started = time.perf_counter()
    chunks = preview_source_document(source)
    return PipelineOutput(
        task_id=source.task_id,
        document_id=source.document_id,
        status="success",
        chunks=chunks,
        total_chunks=len(chunks),
        processing_time_ms=int((time.perf_counter() - started) * 1000),
        errors=[],
    )
