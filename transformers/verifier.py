"""核验校验（MVP：seed chunk 最低结构校验）。

MVP 不实现 Auto-Verified（verification_method='auto' 仅预留，数据中必须为 0 条）。
seed chunk 仍需满足最低结构要求；未通过的保持 unverified 或标记 rejected。
文号缺失与句尾疑似截断不阻断可信来源核验：部分权威文件本身无文号，
且 provider-safe 分块可能在自然语义边界附近截断。
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
    if not chunk.metadata.get("issuing_body"):
        issues.append("missing_issuing_body")
    if not chunk.metadata.get("effective_date"):
        issues.append("missing_effective_date")
    if _looks_like_labor_law_content_under_tax_metadata(chunk):
        issues.append("cross_domain_labor_law_content")

    return len(issues) == 0, issues


def _looks_like_labor_law_content_under_tax_metadata(chunk) -> bool:
    content = chunk.content
    metadata_text = " ".join(
        str(chunk.metadata.get(key) or "")
        for key in ("doc_number", "issuing_body", "source_channel", "doc_type")
    )
    tax_metadata = any(
        marker in metadata_text
        for marker in ("税", "财政", "国家税务总局", "财税")
    )
    labor_contract_rule = (
        "劳动者有下列情形之一" in content
        and "用人单位可以解除劳动合同" in content
    )
    return tax_metadata and labor_contract_rule
