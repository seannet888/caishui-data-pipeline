"""Authenticated service boundary for WebApp -> data-pipeline calls."""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass

from fastapi import Header, HTTPException, Request

from config.settings import get_settings

AUTH_VERSION = "v1"
MAX_CLOCK_SKEW_SECONDS = 300
VALID_ROLES = frozenset({"viewer", "reviewer", "admin"})


@dataclass(frozen=True)
class PipelinePrincipal:
    actor_id: str
    roles: frozenset[str]

    def has_role(self, role: str) -> bool:
        return role in self.roles


def _canonical_message(
    *,
    timestamp: str,
    method: str,
    path: str,
    actor_id: str,
    roles: frozenset[str],
) -> str:
    return "\n".join(
        (
            AUTH_VERSION,
            timestamp,
            method.upper(),
            path,
            actor_id,
            ",".join(sorted(roles)),
        )
    )


async def require_pipeline_principal(
    request: Request,
    version: str | None = Header(None, alias="X-Pipeline-Auth-Version"),
    timestamp: str | None = Header(None, alias="X-Pipeline-Timestamp"),
    actor_id: str | None = Header(None, alias="X-Pipeline-Actor-ID"),
    actor_roles: str | None = Header(None, alias="X-Pipeline-Actor-Roles"),
    signature: str | None = Header(None, alias="X-Pipeline-Signature"),
) -> PipelinePrincipal:
    if not all((version, timestamp, actor_id, signature)):
        raise HTTPException(status_code=401, detail="pipeline_auth_required")
    if version != AUTH_VERSION:
        raise HTTPException(status_code=401, detail="pipeline_auth_invalid")

    settings = get_settings()
    if not settings.pipeline_shared_secret:
        raise HTTPException(status_code=503, detail="pipeline_auth_not_configured")

    roles = frozenset(
        role.strip()
        for role in (actor_roles or "").split(",")
        if role.strip() in VALID_ROLES
    )
    message = _canonical_message(
        timestamp=timestamp,
        method=request.method,
        path=request.url.path,
        actor_id=actor_id,
        roles=roles,
    )
    expected = hmac.new(
        settings.pipeline_shared_secret.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="pipeline_auth_invalid")

    try:
        signed_at = int(timestamp)
    except ValueError as exc:
        raise HTTPException(
            status_code=401, detail="pipeline_auth_invalid"
        ) from exc
    if abs(int(time.time()) - signed_at) > MAX_CLOCK_SKEW_SECONDS:
        raise HTTPException(status_code=401, detail="pipeline_auth_expired")

    return PipelinePrincipal(actor_id=actor_id, roles=roles)
