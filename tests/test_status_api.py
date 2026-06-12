from __future__ import annotations

import hashlib
import hmac
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies import get_ingest_task_repository
from api.routers import status
from config.settings import get_settings


def signed_headers(
    *,
    secret: str,
    method: str,
    path: str,
    timestamp: int,
    actor_id: str = "admin-1",
    roles: str = "admin",
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


class StubTaskRepository:
    def __init__(self, row):
        self.row = row

    async def get_ingest_task(self, task_id: str):
        return self.row


def app_with_repository(repository: StubTaskRepository) -> FastAPI:
    app = FastAPI()
    app.include_router(status.router)
    app.dependency_overrides[get_ingest_task_repository] = lambda: repository
    return app


def test_status_endpoint_returns_persisted_task_progress(monkeypatch):
    secret = "test-pipeline-secret"
    monkeypatch.setenv("PIPELINE_SHARED_SECRET", secret)
    get_settings.cache_clear()
    app = app_with_repository(
        StubTaskRepository(
            {
                "task_id": "task-1",
                "document_id": "doc-1",
                "status": "PROCESSING",
                "completed_chunks": 2,
                "total_chunks": 4,
                "error_message": None,
                "created_at": "2026-06-12T00:00:00Z",
                "started_at": None,
                "completed_at": None,
                "updated_at": "2026-06-12T00:00:01Z",
            }
        )
    )
    client = TestClient(app)

    response = client.get(
        "/status/task-1",
        headers=signed_headers(
            secret=secret,
            method="GET",
            path="/status/task-1",
            timestamp=int(time.time()),
        ),
    )

    assert response.status_code == 200
    assert response.json() == {
        "task_id": "task-1",
        "document_id": "doc-1",
        "status": "PROCESSING",
        "completed_chunks": 2,
        "total_chunks": 4,
        "error_message": None,
        "created_at": "2026-06-12T00:00:00Z",
        "started_at": None,
        "completed_at": None,
        "updated_at": "2026-06-12T00:00:01Z",
        "progress": 0.5,
    }
    get_settings.cache_clear()


def test_status_endpoint_returns_404_for_missing_task(monkeypatch):
    secret = "test-pipeline-secret"
    monkeypatch.setenv("PIPELINE_SHARED_SECRET", secret)
    get_settings.cache_clear()
    app = app_with_repository(StubTaskRepository(None))
    client = TestClient(app)

    response = client.get(
        "/status/missing-task",
        headers=signed_headers(
            secret=secret,
            method="GET",
            path="/status/missing-task",
            timestamp=int(time.time()),
        ),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "task_not_found"}
    get_settings.cache_clear()
