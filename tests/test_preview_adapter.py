from __future__ import annotations

from datetime import date
from pathlib import Path

from ingestion import SourceDocumentInput
from output.preview_adapter import build_preview_output


def test_preview_adapter_returns_pipeline_output_without_embeddings(tmp_path: Path):
    source_path = tmp_path / "研发费用政策.md"
    source_path.write_text(
        """# 研发费用政策

财税〔2024〕15号

第一条 企业发生符合条件的研发费用，可以依照现行规定享受加计扣除政策。
""",
        encoding="utf-8",
    )
    source = SourceDocumentInput(
        task_id="preview-task",
        document_id="preview-doc",
        file_path=str(source_path),
        file_name=source_path.name,
        file_hash="e" * 64,
        title="研发费用政策",
        source_channel="财政部官网",
        issuing_body="财政部、国家税务总局",
        jurisdiction="全国",
        doc_type="notice",
        effective_date=date(2024, 1, 1),
        source_section="正文",
    )

    result = build_preview_output(source)

    assert result.task_id == "preview-task"
    assert result.document_id == "preview-doc"
    assert result.status == "success"
    assert result.total_chunks == len(result.chunks) == 1
    assert result.errors == []
    assert result.chunks[0].embedding is None
    assert result.chunks[0].embedding_model is None
    assert result.chunks[0].metadata.doc_number == "财税〔2024〕15号"
