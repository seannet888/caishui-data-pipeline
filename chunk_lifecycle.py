"""Knowledge Chunk lifecycle decisions.

The module owns the rule that a stable Chunk Location has at most one current
version and that identical reprocessing cannot erase trusted operational state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


LifecycleAction = Literal["create_initial", "preserve_current", "create_version"]


@dataclass(frozen=True)
class ChunkLifecycleDecision:
    action: LifecycleAction
    previous_row_id: str | None = None


_PRESERVED_FIELDS = (
    "row_id",
    "verification_status",
    "verification_method",
    "verified_by",
    "verified_at",
    "verification_notes",
    "embedding",
    "embedding_status",
    "embedding_error",
    "embedding_identity",
    "embedding_model",
    "embedding_dimension",
    "embedding_attempts",
    "embedding_last_attempt_at",
)


def reconcile_chunk(candidate, current) -> ChunkLifecycleDecision:
    """Reconcile one incoming chunk against the current row at its location."""
    if current is None:
        return ChunkLifecycleDecision(action="create_initial")

    if current.content_hash != candidate.content_hash:
        return ChunkLifecycleDecision(
            action="create_version",
            previous_row_id=current.row_id,
        )

    for field in _PRESERVED_FIELDS:
        setattr(candidate, field, getattr(current, field))
    return ChunkLifecycleDecision(
        action="preserve_current",
        previous_row_id=current.row_id,
    )
