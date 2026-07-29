"""FastAPI 应用入口。"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routers import compliance, export, generation, history, platforms, prompts, settings, system
from app.core import config
from app.core.data_loader import load_data
from app.repositories import db


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.prepare_runtime_files()
    db.init_db()
    app.state.compliance_load_error = None
    try:
        store = load_data()
        if not store.validation.get("valid"):
            app.state.compliance_load_error = "；".join(store.validation.get("errors", []))
            print(f"[WARN] 规则库校验存在错误：{app.state.compliance_load_error}")
    except Exception as exc:
        app.state.compliance_load_error = str(exc)
        print(f"[WARN] 规则库加载失败：{exc}")
    yield
    db.close_db()


app = FastAPI(
    title="AI医美内容合规工作台",
    description="企业内部轻量级工具：内容生成、风险检测、规则解释与人工复核摘要。",
    version="1.3.0",
    lifespan=lifespan,
)

cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5174,http://127.0.0.1:5174").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(system.router)
app.include_router(platforms.router)
app.include_router(prompts.router)
app.include_router(generation.router)
app.include_router(compliance.router)
app.include_router(history.router)
app.include_router(settings.router)
app.include_router(export.router)

_frontend_index = config.FRONTEND_DIST_DIR / "index.html"
_frontend_assets = config.FRONTEND_DIST_DIR / "assets"
if _frontend_assets.exists():
    app.mount("/assets", StaticFiles(directory=str(_frontend_assets)), name="frontend-assets")


@app.get("/")
def root():
    if _frontend_index.exists():
        return FileResponse(_frontend_index)
    return {
        "name": "AI医美内容合规工作台",
        "version": app.version,
        "docs": "/docs",
        "api": "/api/status",
    }


if _frontend_index.exists():
    @app.get("/{full_path:path}", include_in_schema=False)
    def frontend_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        return FileResponse(_frontend_index)
