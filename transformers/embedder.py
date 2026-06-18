"""向量化（硅基流动 SiliconFlow + BAAI/bge-large-zh-v1.5，1024 维，见 ADR-0006）。

使用 openai SDK，配置 base_url 调用硅基流动。维度锁定 1024，独立于 DeepSeek chat。
"""

from __future__ import annotations

import asyncio
import logging

from openai import AsyncOpenAI, RateLimitError

from config.settings import get_settings

logger = logging.getLogger(__name__)

_MAX_RETRIES = 5
_BASE_DELAY = 2.0


class Embedder:
    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.embedding_model
        self.dimension = settings.embedding_dimension
        self._client = AsyncOpenAI(
            api_key=settings.embedding_api_key,
            base_url=settings.embedding_base_url,
        )

    async def embed(self, text: str) -> list[float]:
        for attempt in range(_MAX_RETRIES):
            try:
                resp = await self._client.embeddings.create(
                    model=self.model, input=text
                )
                vector = resp.data[0].embedding
                if len(vector) != self.dimension:
                    raise ValueError(
                        f"embedding_dimension_mismatch: got {len(vector)}, expected {self.dimension}"
                    )
                return vector
            except RateLimitError:
                if attempt == _MAX_RETRIES - 1:
                    raise
                delay = _BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "embedding rate-limited, retrying in %.0fs (attempt %d/%d)",
                    delay, attempt + 1, _MAX_RETRIES,
                )
                await asyncio.sleep(delay)
