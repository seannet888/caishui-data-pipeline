"""抽象基类 BaseLoader：所有 loader 统一输出 Markdown + 页面元数据。"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field


@dataclass
class LoadResult:
    markdown: str
    page_metadata: dict = field(default_factory=dict)


class BaseLoader(abc.ABC):
    @abc.abstractmethod
    def load(self, file_path: str) -> LoadResult:
        """解析文件，返回 Markdown 文本与页面级元数据。"""
        raise NotImplementedError
