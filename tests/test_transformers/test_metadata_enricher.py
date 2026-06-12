"""metadata_enricher 单测：authority_rank 推断与 publish_date 抽取。"""

from __future__ import annotations

from datetime import date

from transformers.metadata_enricher import extract_publish_date, infer_authority_rank


def test_infer_authority_rank_normative_document():
    assert infer_authority_rank({"doc_number": "财税〔2023〕6号"}) == 70


def test_infer_authority_rank_law():
    assert infer_authority_rank({"issuing_body": "全国人民代表大会常务委员会"}) == 100


def test_infer_authority_rank_unknown_returns_none():
    assert infer_authority_rank({"title": "某参考资料"}) is None


def test_extract_publish_date_prefers_page_metadata():
    got = extract_publish_date("正文无日期", {"published_at": "2023-03-26"})
    assert got == date(2023, 3, 26)


def test_extract_publish_date_from_text():
    got = extract_publish_date("……\n2023年3月26日发布", {})
    assert got == date(2023, 3, 26)
