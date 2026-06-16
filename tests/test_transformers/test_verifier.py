"""seed verifier tests."""

from __future__ import annotations

from types import SimpleNamespace

from transformers.verifier import validate_seed_chunk


def test_seed_chunk_allows_official_source_without_doc_number_or_sentence_end():
    chunk = SimpleNamespace(
        content="第一条 根据中华人民共和国增值税法制定本条例，本段因安全分块可能停在逗号，",
        metadata={
            "source_section": "正文",
            "doc_number": None,
            "issuing_body": "国务院",
            "effective_date": "2026-01-01",
        },
    )

    ok, issues = validate_seed_chunk(chunk)

    assert ok is True
    assert issues == []


def test_seed_chunk_still_rejects_missing_core_source_metadata():
    chunk = SimpleNamespace(
        content="第一条 本段内容足够长，但缺少来源位置、发文机关和生效日期，因此不能作为可信来源自动核验结果。",
        metadata={},
    )

    ok, issues = validate_seed_chunk(chunk)

    assert ok is False
    assert issues == [
        "missing_source_location",
        "missing_issuing_body",
        "missing_effective_date",
    ]


def test_seed_chunk_rejects_cross_domain_labor_law_content_under_tax_metadata():
    chunk = SimpleNamespace(
        content=(
            "第三十九条 劳动者有下列情形之一的，用人单位可以解除劳动合同：\n"
            "（一）在试用期间被证明不符合录用条件的；\n"
            "《中华人民共和国个人所得税法实施条例》（国令第707号）"
        ),
        metadata={
            "source_section": "正文",
            "doc_number": "国家税务总局公告2016年第16号",
            "issuing_body": "国家税务总局",
            "effective_date": "2016-01-01",
        },
    )

    ok, issues = validate_seed_chunk(chunk)

    assert ok is False
    assert issues == ["cross_domain_labor_law_content"]
