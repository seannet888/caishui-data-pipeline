import hashlib
import hmac
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.main import app as pipeline_app
from api.routers import ingest, preview, status
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
        ("v1", str(timestamp), "POST", "/ingest", actor_id, normalized_roles)
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


def test_ingest_rejects_request_without_service_signature():
    app = FastAPI()
    app.include_router(ingest.router)
    client = TestClient(app)

    response = client.post(
        "/ingest",
        files={"file": ("policy.md", b"tax policy", "text/markdown")},
        data={
            "document_id": "doc-1",
            "file_hash": "0" * 64,
            "title": "Policy",
        },
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "pipeline_auth_required"}


def test_pipeline_startup_fails_when_shared_secret_is_missing(monkeypatch):
    monkeypatch.delenv("PIPELINE_SHARED_SECRET", raising=False)
    get_settings.cache_clear()

    with pytest.raises(
        RuntimeError, match="PIPELINE_SHARED_SECRET must be configured"
    ):
        with TestClient(pipeline_app):
            pass

    get_settings.cache_clear()


def test_valid_signature_reaches_ingest_business_validation(monkeypatch):
    secret = "test-pipeline-secret"
    monkeypatch.setenv("PIPELINE_SHARED_SECRET", secret)
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(ingest.router)
    client = TestClient(app)

    response = client.post(
        "/ingest",
        headers=signed_headers(
            secret=secret,
            timestamp=int(time.time()),
        ),
        files={"file": ("policy.md", b"tax policy", "text/markdown")},
        data={
            "document_id": "doc-1",
            "file_hash": "0" * 64,
            "title": "Policy",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "uploaded_file_hash_mismatch"}
    get_settings.cache_clear()


def test_tampered_actor_roles_invalidate_signature(monkeypatch):
    secret = "test-pipeline-secret"
    monkeypatch.setenv("PIPELINE_SHARED_SECRET", secret)
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(ingest.router)
    client = TestClient(app)
    headers = signed_headers(
        secret=secret,
        timestamp=int(time.time()),
        actor_id="viewer-1",
        roles="viewer",
    )
    headers["X-Pipeline-Actor-Roles"] = "admin"

    response = client.post(
        "/ingest",
        headers=headers,
        files={"file": ("policy.md", b"tax policy", "text/markdown")},
        data={
            "document_id": "doc-1",
            "file_hash": "0" * 64,
            "title": "Policy",
        },
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "pipeline_auth_invalid"}
    get_settings.cache_clear()


def test_preview_and_status_also_require_service_signature():
    app = FastAPI()
    app.include_router(preview.router)
    app.include_router(status.router)
    client = TestClient(app)

    preview_response = client.post(
        "/preview",
        files={"file": ("policy.md", b"tax policy", "text/markdown")},
    )
    status_response = client.get("/status/task-1")

    assert preview_response.status_code == 401
    assert status_response.status_code == 401


def test_ingest_rejects_expired_signed_request(monkeypatch):
    secret = "test-pipeline-secret"
    monkeypatch.setenv("PIPELINE_SHARED_SECRET", secret)
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(ingest.router)
    client = TestClient(app)

    response = client.post(
        "/ingest",
        headers=signed_headers(
            secret=secret,
            timestamp=int(time.time()) - 301,
        ),
        files={"file": ("policy.md", b"tax policy", "text/markdown")},
        data={
            "document_id": "doc-1",
            "file_hash": "0" * 64,
            "title": "Policy",
        },
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "pipeline_auth_expired"}
    get_settings.cache_clear()


def test_seed_ingest_requires_admin_role_from_signed_principal(monkeypatch):
    secret = "test-pipeline-secret"
    monkeypatch.setenv("PIPELINE_SHARED_SECRET", secret)
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(ingest.router)
    client = TestClient(app)
    content = b"tax policy"

    response = client.post(
        "/ingest",
        headers=signed_headers(
            secret=secret,
            timestamp=int(time.time()),
            actor_id="reviewer-1",
            roles="reviewer",
        ),
        files={"file": ("policy.md", content, "text/markdown")},
        data={
            "document_id": "doc-1",
            "file_hash": hashlib.sha256(content).hexdigest(),
            "title": "Policy",
            "verification_method": "seed",
            "seed_batch_id": "seed-1",
        },
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "seed_requires_admin"}
    get_settings.cache_clear()
