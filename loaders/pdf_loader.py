"""PDF 解析（pymupdf4llm，保留布局，输出 Markdown）。"""

from __future__ import annotations

from .base_loader import BaseLoader, LoadResult


class PdfLoader(BaseLoader):
    def load(self, file_path: str) -> LoadResult:
        # 延迟导入，避免无 PDF 任务时加载依赖
        import pymupdf4llm

        markdown = pymupdf4llm.to_markdown(file_path)
        # TODO(scaffold): 提取页码映射、扫描件 OCR 置信度等页面元数据。
        return LoadResult(markdown=markdown, page_metadata={})
