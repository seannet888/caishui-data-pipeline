"""Pydantic BaseSettings 配置管理。"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://caishui:localdev_password@localhost:5432/caishui_db"

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    # Embedding 提供商独立于 DeepSeek（见 ADR-0006）：硅基流动 + BAAI/bge-large-zh-v1.5。
    # ⚠️ 维度锁定：1024 是数据库 Schema 与所有索引的硬约束。禁止运行时切换不同维度模型。
    embedding_base_url: str = "https://api.siliconflow.cn/v1"
    embedding_api_key: str = ""
    embedding_model: str = "BAAI/bge-large-zh-v1.5"
    embedding_dimension: int = 1024

    storage_dir: str = "./_storage"
    pipeline_shared_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
