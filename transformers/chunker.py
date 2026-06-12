"""财税语义分块（纯正则规则，不依赖 LLM）。

核心原则：保留财税法规结构完整性，避免切断条款、表格和列表项，
控制 chunk 大小适配 embedding 模型。

参数（tokens，近似按字符估算）：目标 512 / 最大 1024 / 最小 50 / 重叠 50。
降级：无明确条款编号时退化为按段落（\\n\\n）切分。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

TARGET_CHUNK_TOKENS = 512
MAX_CHUNK_TOKENS = 1024
MIN_CHUNK_TOKENS = 50
OVERLAP_TOKENS = 50

# 条款边界：几乎所有正式财税法规使用此格式
CLAUSE_PATTERN = re.compile(r"(?=^第[零一二三四五六七八九十百千万\d]+[条款章节]\s)", re.MULTILINE)
HEADING_PATTERN = re.compile(r"(?=^#{1,2}\s)", re.MULTILINE)
TABLE_LINE = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)


@dataclass
class Chunk:
    content: str
    chunk_index: int
    chunk_type: str = "text"  # "text" | "table" | "image_caption"


def _approx_tokens(text: str) -> int:
    # 中文近似：1 token ≈ 1 字符；此处用字符数粗略估算，生产可换 tokenizer。
    return len(text)


def _split_long(text: str) -> list[str]:
    """超长条款（> MAX）按句号/分号二次切分。"""
    if _approx_tokens(text) <= MAX_CHUNK_TOKENS:
        return [text]
    parts = re.split(r"(?<=[。；;])", text)
    out: list[str] = []
    buf = ""
    for p in parts:
        if _approx_tokens(buf + p) > TARGET_CHUNK_TOKENS and buf:
            out.append(buf)
            buf = p
        else:
            buf += p
    if buf:
        out.append(buf)
    return out


def chunk_markdown(markdown: str) -> list[Chunk]:
    """对 pymupdf4llm 生成的 Markdown 做财税语义分块。"""
    segments = _segment(markdown)
    chunks: list[Chunk] = []
    index = 0
    pending = ""  # 用于合并过短片段

    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue

        # 表格整体保留为一个 chunk，不拆分行
        if TABLE_LINE.search(seg):
            if pending:
                chunks.append(Chunk(pending, index)); index += 1; pending = ""
            chunks.append(Chunk(seg, index, "table")); index += 1
            continue

        for piece in _split_long(seg):
            if _approx_tokens(piece) < MIN_CHUNK_TOKENS:
                pending = (pending + "\n" + piece).strip()
                continue
            if pending:
                piece = (pending + "\n" + piece).strip()
                pending = ""
            chunks.append(Chunk(piece, index)); index += 1

    if pending:
        chunks.append(Chunk(pending, index))

    return chunks


def _segment(markdown: str) -> list[str]:
    """先按标题层级，再按条款边界切分；无条款编号时降级为按段落。"""
    by_heading = HEADING_PATTERN.split(markdown)
    segments: list[str] = []
    for block in by_heading:
        if CLAUSE_PATTERN.search(block):
            segments.extend(CLAUSE_PATTERN.split(block))
        else:
            # 降级：按空行段落切分
            segments.extend(re.split(r"\n{2,}", block))
    return segments
