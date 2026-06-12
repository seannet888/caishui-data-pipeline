"""Pipeline Writer Adapter。

保留 persist_chunk 作为 ingestion 的稳定入口；生产 embedding 生命周期规则由
output.embedding_lifecycle 承担。Seed-Verified 仍在这里保留为 writer 前的信任标记步骤。
"""

from __future__ import annotations

from datetime import UTC, datetime

from output.embedding_lifecycle import (
    ChunkRepository,
    EmbedderProtocol,
    apply_embedding_lifecycle,
)


async def persist_chunk(chunk, embedder: EmbedderProtocol, repo: ChunkRepository) -> None:
    await apply_embedding_lifecycle(chunk, embedder, repo)


def mark_seed_verified(chunk, seed_batch_id: str, imported_by: str) -> None:
    """Seed-Verified：逐 chunk 标记，禁止整份文件一键 verified。"""
    from transformers.verifier import validate_seed_chunk

    ok, issues = validate_seed_chunk(chunk)
    if not ok:
        chunk.verification_status = "unverified"
        chunk.verification_method = "seed"
        chunk.verification_notes = f"Seed chunk failed validation: {', '.join(issues)}"
        return

    chunk.verification_status = "verified"
    chunk.verification_method = "seed"
    chunk.verified_by = f"{seed_batch_id}:{imported_by}"
    chunk.verified_at = datetime.now(UTC)
    chunk.verification_notes = (
        "MVP seed corpus; official source manually selected for prototype validation."
    )
