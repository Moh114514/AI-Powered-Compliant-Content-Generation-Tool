"""FastAPI 应用入口。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.data_loader import load_data
from app.repositories import db
from app.api.routers import system, platforms, generation, compliance, history, settings, export
from app.core.responses import fail

app = FastAPI(
    title="AI医美内容合规工作台",
    description="企业内部轻量级合规工具：内容生成、风险检测、人工复核摘要。纯工具型，不含用户/权限/审批。",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    # 初始化数据库
    db.init_db()
    # 加载规则库（只读）
    try:
        load_data()
    except Exception as e:
        # 启动时不阻断，但 /api/status 会报错提示
        print(f"[WARN] 规则库加载失败：{e}")


app.include_router(system.router)
app.include_router(platforms.router)
app.include_router(generation.router)
app.include_router(compliance.router)
app.include_router(history.router)
app.include_router(settings.router)
app.include_router(export.router)


@app.get("/")
def root():
    return {"name": "AI医美内容合规工作台", "docs": "/docs", "api": "/api/status"}
