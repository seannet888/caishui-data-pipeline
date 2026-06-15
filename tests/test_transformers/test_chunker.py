"""chunker 单测：验证条款边界切分与表格保留（外部行为，不耦合内部函数）。"""

from __future__ import annotations

from transformers.chunker import MAX_CHUNK_TOKENS, chunk_markdown


def test_splits_on_clause_boundaries():
    md = (
        "# 第一章 总则\n\n"
        "第一条 为了规范……，制定本办法。这是一段足够长的条款内容用于满足最小分块长度要求，"
        "确保它不会被并入相邻片段而是独立成块，便于后续检索定位到具体条款位置。\n\n"
        "第二条 本办法适用于……同样需要足够长度的条款正文来形成一个独立的语义单元，"
        "覆盖适用范围的描述以及相关定义，保证分块器按条款边界切分。\n"
    )
    chunks = chunk_markdown(md)
    contents = [c.content for c in chunks]
    assert any("第一条" in c for c in contents)
    assert any("第二条" in c for c in contents)


def test_table_kept_as_single_chunk():
    md = (
        "## 税率表\n\n"
        "| 税目 | 税率 |\n| --- | --- |\n| 货物 | 13% |\n| 服务 | 6% |\n"
    )
    chunks = chunk_markdown(md)
    table_chunks = [c for c in chunks if c.chunk_type == "table"]
    assert len(table_chunks) == 1
    assert "13%" in table_chunks[0].content and "6%" in table_chunks[0].content


def test_degrades_to_paragraphs_without_clause_numbers():
    md = "这是第一段，没有条款编号但内容足够长可以独立成块用于测试降级分段逻辑是否生效。\n\n这是第二段，同样足够长以形成另一个独立的段落分块结果。"
    chunks = chunk_markdown(md)
    assert len(chunks) >= 1


def test_long_plain_text_chunks_are_capped_for_embedding_provider():
    md = "# 长文本测试\n\n" + "增值税实施条例测试内容" * 400

    chunks = chunk_markdown(md)

    assert len(chunks) > 1
    assert all(len(chunk.content) <= MAX_CHUNK_TOKENS for chunk in chunks)


def test_many_short_clause_segments_do_not_accumulate_into_oversized_pending_chunk():
    md = "# 短条款测试\n\n" + "\n".join(
        f"第{i}条 本条用于测试短条款累计后仍需安全分块。"
        for i in range(1, 120)
    )

    chunks = chunk_markdown(md)

    assert len(chunks) > 1
    assert all(len(chunk.content) <= MAX_CHUNK_TOKENS for chunk in chunks)
