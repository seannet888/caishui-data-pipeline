"""财税元数据抽取（纯正则，不调用 LLM）。

MVP 仅填充：doc_number, article_number, publish/effective/expire date,
jurisdiction, issuing_body, source_channel, source_page/section, has_table,
has_formula, doc_type, authority_rank。
publish_date 优先用官方页面元数据，其次匹配标题区/落款；source_channel 来自
上传/抓取时的来源配置，不能用 issuing_body 冒充。
"""

from __future__ import annotations

import re
from datetime import date


def infer_authority_rank(metadata: dict) -> int | None:
    """推断效力层级。无法判定时返回 None（检索排序按中性层级处理，不伪造高层级）。"""
    title = metadata.get("title") or ""
    doc_number = metadata.get("doc_number") or ""
    issuing_body = metadata.get("issuing_body") or ""

    if "全国人民代表大会" in issuing_body or "主席令" in doc_number:
        return 100
    if "国务院" in issuing_body or "国务院令" in doc_number:
        return 90
    if "规章" in title and ("财政部" in issuing_body or "国家税务总局" in issuing_body):
        return 80
    if doc_number.startswith("财税") or "国家税务总局公告" in title:
        return 70
    if "省税务局" in issuing_body or "市税务局" in issuing_body or "地方税务局" in issuing_body:
        return 60
    if "解读" in title or "答记者问" in title:
        return 50
    if "案例" in title:
        return 40
    return None


def _parse_date(year: str, month: str, day: str) -> date:
    return date(int(year), int(month), int(day))


def first_matching_date(text: str, patterns: list[str]) -> date | None:
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return _parse_date(m.group(1), m.group(2), m.group(3))
    return None


def extract_publish_date(text: str, page_metadata: dict) -> date | None:
    """优先使用官方页面元数据，其次匹配标题区或落款中的明确发布日期。"""
    if page_metadata.get("published_at"):
        raw = page_metadata["published_at"]
        m = re.match(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", str(raw))
        if m:
            return _parse_date(m.group(1), m.group(2), m.group(3))

    patterns = [
        r"(20\d{2})年(\d{1,2})月(\d{1,2})日发布",
        r"发布日期[：:]\s*(20\d{2})[-年](\d{1,2})[-月](\d{1,2})日?",
        r"(20\d{2})年(\d{1,2})月(\d{1,2})日\s*$",
    ]
    return first_matching_date(text, patterns)


def extract_doc_number(text: str) -> str | None:
    m = re.search(r"财税〔\d{4}〕\d+号|国家税务总局公告\d{4}年第\d+号", text)
    return m.group(0) if m else None


def detect_has_table(markdown: str) -> bool:
    return "|" in markdown and re.search(r"\|.*\|", markdown) is not None


def detect_has_formula(text: str) -> bool:
    return bool(re.search(r"[＝=].*[+\-×*/]|应纳税额|计算公式", text))
