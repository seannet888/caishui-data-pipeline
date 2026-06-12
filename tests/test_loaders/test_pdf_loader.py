"""pdf_loader 单测占位。

放入 tests/fixtures/sample.pdf 后，断言解析输出包含预期标题层级与表格结构。
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="需要 tests/fixtures/sample.pdf 与 pymupdf4llm 环境")
def test_pdf_loader_outputs_markdown():
    from loaders.pdf_loader import PdfLoader

    result = PdfLoader().load("tests/fixtures/sample.pdf")
    assert result.markdown
