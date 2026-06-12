"""核验校验（MVP：seed chunk 最低结构校验）。

MVP 不实现 Auto-Verified（verification_method='auto' 仅预留，数据中必须为 0 条）。
seed chunk 仍需满足最低结构要求；未通过的保持 unverified 或标记 rejected。
"""

from __future__ import annotations


class _ChunkLike:
    """鸭子类型：具备 content 与 metadata(dict) 的 chunk。"""

    content: str
    metadata: dict


def validate_seed_chunk(chunk) -> tuple[bool, list[str]]:
    issues: list[str] = []
    if len(chunk.content.strip()) <= 20:
        issues.append("content_too_short")
    if not chunk.metadata.get("source_page") and not chunk.metadata.get("source_section"):
        issues.append("missing_source_location")
    if not chunk.metadata.get("doc_number"):
        issues.append("missing_doc_number")
    if not chunk.metadata.get("issuing_body"):
        issues.append("missing_issuing_body")
    if not chunk.metadata.get("effective_date"):
        issues.append("missing_effective_date")
    if chunk.content.rstrip().endswith(("，", "、", "；")):
        issues.append("possible_truncated_sentence")

    return len(issues) == 0, issues
