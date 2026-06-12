from __future__ import annotations

import hashlib
import hmac
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import preview
from config.settings import get_settings


def signed_headers(
    *,
    secret: str,
    timestamp: int,
    actor_id: str = "admin-1",
    roles: str = "admin",
) -> dict[str, str]:
    normalized_roles = ",".join(sorted(filter(None, roles.split(","))))
    message = "\n".join(
        ("v1", str(timestamp), "POST", "/preview", actor_id, normalized_roles)
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


def test_preview_endpoint_returns_pipeline_output_without_persistence_or_embedding(
    monkeypatch,
):
    secret = "test-pipeline-secret"
    monkeypatch.setenv("PIPELINE_SHARED_SECRET", secret)
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(preview.router)
    client = TestClient(app)
    content = """# 研发费用政策

财税〔2024〕15号

第一条 企业发生符合条件的研发费用，可以依照现行规定享受加计扣除政策。
""".encode()

    response = client.post(
        "/preview",
        headers=signed_headers(secret=secret, timestamp=int(time.time())),
        files={"file": ("policy.md", content, "text/markdown")},
        data={
            "title": "研发费用政策",
            "source_channel": "财政部官网",
            "issuing_body": "财政部、国家税务总局",
            "jurisdiction": "全国",
            "doc_type": "notice",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "preview"
    assert body["document_id"] == "preview"
    assert body["status"] == "success"
    assert body["total_chunks"] == 1
    assert body["errors"] == []
    assert body["chunks"][0]["embedding"] is None
    assert body["chunks"][0]["embedding_model"] is None
    assert body["chunks"][0]["metadata"]["doc_number"] == "财税〔2024〕15号"
    get_settings.cache_clear()
