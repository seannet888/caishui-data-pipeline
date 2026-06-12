"""Excel/CSV 解析（pandas，表格转结构化 Markdown 文本）。"""

from __future__ import annotations

from pathlib import Path

from .base_loader import BaseLoader, LoadResult


class ExcelLoader(BaseLoader):
    def load(self, file_path: str) -> LoadResult:
        import pandas as pd

        suffix = Path(file_path).suffix.lower()
        if suffix == ".csv":
            frames = {"sheet1": pd.read_csv(file_path)}
        else:
            frames = pd.read_excel(file_path, sheet_name=None)

        blocks: list[str] = []
        for name, df in frames.items():
            blocks.append(f"## {name}\n\n{df.to_markdown(index=False)}")
        return LoadResult(markdown="\n\n".join(blocks), page_metadata={})
