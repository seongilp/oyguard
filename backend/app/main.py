"""FastAPI application entrypoint for oy-guard."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.routes import router
from .core.config import get_settings
from .models import Envelope
from .services.jobs import store

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Restore persisted jobs so work survives a backend restart.
    store.load_all()
    yield


app = FastAPI(
    title="oy-guard",
    description="컨테이너 이미지 취약점 스캔 · 조치 · 서명 시스템",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=Envelope.fail(str(exc.detail)).model_dump())


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content=Envelope.fail(str(exc)).model_dump())


@app.get("/")
async def root() -> dict:
    return {"name": "oy-guard", "docs": "/docs", "health": "/api/health"}
