"""Markdown 解析（保留标题层级，提取代码块）。"""

from __future__ import annotations

from pathlib import Path

from .base_loader import BaseLoader, LoadResult


class MdLoader(BaseLoader):
    def load(self, file_path: str) -> LoadResult:
        markdown = Path(file_path).read_text(encoding="utf-8")
        return LoadResult(markdown=markdown, page_metadata={})
