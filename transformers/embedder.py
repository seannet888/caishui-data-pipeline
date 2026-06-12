"""向量化（硅基流动 SiliconFlow + BAAI/bge-large-zh-v1.5，1024 维，见 ADR-0006）。

使用 openai SDK，配置 base_url 调用硅基流动。维度锁定 1024，独立于 DeepSeek chat。
"""

from __future__ import annotations

from openai import AsyncOpenAI

from config.settings import get_settings


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
        resp = await self._client.embeddings.create(model=self.model, input=text)
        vector = resp.data[0].embedding
        if len(vector) != self.dimension:
            raise ValueError(
                f"embedding_dimension_mismatch: got {len(vector)}, expected {self.dimension}"
            )
        return vector
