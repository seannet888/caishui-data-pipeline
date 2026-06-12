# data-pipeline/output/schemas.py
# 标准输出 JSON 契约 v1.0
# 与 caishui-webapp/types/pipeline.ts 保持结构同步（铁律三）。

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────
# 枚举
# ─────────────────────────────────────────────


class DocType(str, Enum):
    REGULATION = "regulation"
    ANNOUNCEMENT = "announcement"
    NOTICE = "notice"
    INTERPRETATION = "interpretation"
    CASE = "case"
    GUIDE = "guide"


class ChunkType(str, Enum):
    TEXT = "text"
    TABLE = "table"
    IMAGE_CAPTION = "image_caption"


# ─────────────────────────────────────────────
# 财税专用 Metadata Schema
# ─────────────────────────────────────────────


class TaxMetadata(BaseModel):
    """财税领域专用元数据，嵌入 ChunkOutput.metadata 字段。
    MVP 阶段仅使用正则 + 文档级解析填充，不调用 LLM。"""

    # 文件标识（正则从文件名/文档开头抽取）
    doc_number: Optional[str] = Field(None, description="文号，如'财税〔2023〕06号'")
    article_number: Optional[str] = Field(None, description="条款号，如'第十二条第二款'")

    # 时效信息（正则匹配"自X年X月X日起施行"等模式）
    publish_date: Optional[date] = Field(None, description="官方发布日期；无明确日期时留空")
    effective_date: Optional[date] = Field(None, description="本条款生效日期")
    expire_date: Optional[date] = Field(None, description="本条款失效日期，null 表示仍有效")
    is_expired: bool = Field(False, description="是否已过期（便于快速过滤）")

    # 地域与发文机关（正则从文档头部抽取）
    jurisdiction: Optional[str] = Field(None, description="管辖地：'全国'/'上海市'等")
    issuing_body: Optional[str] = Field(None, description="发文机关")
    source_channel: Optional[str] = Field(None, description="采集/发布渠道名称")

    # 来源位置（从 PDF 解析和 Markdown 标题直接获取）
    source_page: Optional[int] = Field(None, description="来源页码（PDF）")
    source_section: Optional[str] = Field(None, description="来源章节标题")

    # 结构标记（正则检测）
    has_table: bool = Field(False, description="是否包含表格")
    has_formula: bool = Field(False, description="是否包含计算公式")

    # 检索/排序冗余字段
    doc_type: Optional[DocType] = Field(None, description="文档类型")
    authority_rank: Optional[int] = Field(None, description="效力层级，null 表示未知")

    # 以下字段 MVP 不实现，留空或设默认值（tax_category, industry, tax_rates,
    # threshold_amounts, related_forms, keywords 等），未来可通过离线 LLM 批量补充。


# ─────────────────────────────────────────────
# Chunk 输出结构
# ─────────────────────────────────────────────


class ChunkOutput(BaseModel):
    """单个 Chunk 的标准输出结构"""

    chunk_id: str = Field(
        ...,
        description="Pipeline 稳定位置 ID：SHA256(file_hash + chunk_index)。写库后保存为 pipeline_chunk_id。",
    )
    document_id: str = Field(..., description="所属文档 ID")
    chunk_index: int = Field(..., ge=0, description="在文档中的顺序索引（从 0 开始）")
    chunk_type: ChunkType = Field(ChunkType.TEXT)

    content: str = Field(..., min_length=1, description="chunk 原文（已清洗）")
    content_hash: str = Field(..., description="content 的 SHA-256 hex（去重用）")

    embedding: Optional[list[float]] = Field(
        None, description="向量表示（BAAI/bge-large-zh-v1.5 @ 硅基流动: 1024维）"
    )
    embedding_model: Optional[str] = Field(None, description="生成 embedding 使用的模型名称")

    metadata: TaxMetadata = Field(default_factory=TaxMetadata)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ─────────────────────────────────────────────
# 完整清洗任务的顶层输出结构
# ─────────────────────────────────────────────


class PipelineOutput(BaseModel):
    """清洗任务完整输出，作为写入数据库的最终交付物"""

    task_id: str
    document_id: str
    status: Literal["success", "partial_failure", "failed"] = Field(
        ..., description="'success' | 'partial_failure' | 'failed'"
    )

    chunks: list[ChunkOutput] = Field(default_factory=list)

    total_chunks: int = 0
    processing_time_ms: int = 0

    errors: list[str] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
