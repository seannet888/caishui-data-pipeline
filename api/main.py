"""FastAPI 入口，挂载所有路由。"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routers import ingest, preview, status
from config.settings import get_settings
from db.connection import engine
from db.recovery import reclaim_orphaned_tasks
from db.schema_check import check_ingest_tasks_schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not get_settings().pipeline_shared_secret:
        raise RuntimeError("PIPELINE_SHARED_SECRET must be configured")
    # 启动即校验 ingest_tasks 与 Prisma 管理的真实表一致（见 ADR-0007）。
    await check_ingest_tasks_schema(engine)
    # 回收上一进程遗留的孤儿任务（见 ADR-0008）。
    await reclaim_orphaned_tasks(engine)
    yield


app = FastAPI(title="caishui-data-pipeline", version="0.1.0", lifespan=lifespan)

app.include_router(ingest.router, tags=["ingest"])
app.include_router(status.router, tags=["status"])
app.include_router(preview.router, tags=["preview"])


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
