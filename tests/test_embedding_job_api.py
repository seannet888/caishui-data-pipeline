from __future__ import annotations

import hashlib
import hmac
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies import get_embedding_job_repository, get_embedder
from api.routers import embedding
from config.settings import get_settings


def signed_headers(
    *,
    secret: str,
    method: str,
    path: str,
    timestamp: int,
    actor_id: str = "reviewer-1",
    roles: str = "reviewer",
) -> dict[str, str]:
    normalized_roles = ",".join(sorted(filter(None, roles.split(","))))
    message = "\n".join(
        ("v1", str(timestamp), method, path, actor_id, normalized_roles)
    )
    signature = hmac.new(
        secret.encode(), message.encode(), hashlib.sha256
    ).hexdigest()
    return {
        "X-Pipeline-Auth-Version": "v1",
        "X-Pipeline-Timestamp": str(timestamp),
        "X-Pipeline-Actor-ID": actor_id,
        "X-Pipeline-Actor-Roles": roles,
        "X-Pipeline-Signature": signature,
    }


def test_embedding_endpoint_accepts_signed_request_and_schedules_job(monkeypatch):
    secret = "test-pipeline-secret"
    monkeypatch.setenv("PIPELINE_SHARED_SECRET", secret)
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(embedding.router)
    app.dependency_overrides[get_embedder] = lambda: "embedder"
    app.dependency_overrides[get_embedding_job_repository] = lambda: "repo"
    calls = []

    async def fake_run_embedding_job(*args):
        calls.append(args)

    monkeypatch.setattr(embedding, "run_embedding_job", fake_run_embedding_job)
    client = TestClient(app)

    response = client.post(
        "/chunks/chunk-1/embed",
        headers=signed_headers(
            secret=secret,
            method="POST",
            path="/chunks/chunk-1/embed",
            timestamp=int(time.time()),
        ),
    )

    assert response.status_code == 202
    assert response.json() == {
        "chunk_id": "chunk-1",
        "status": "QUEUED",
    }
    assert calls == [("chunk-1", "embedder", "repo")]
    get_settings.cache_clear()
