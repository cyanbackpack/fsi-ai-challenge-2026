"""FastAPI entrypoint."""

from __future__ import annotations

import logging

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.ai.client import ClaudeClient
from app.ai.engine import HybridEngine
from app.ai.rulesets import build_engine
from app.ai.schemas import AnalysisRequest, AnalysisResult
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO)

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

engine = HybridEngine(rules=build_engine(), llm=ClaudeClient(settings))

INDEX = Path(__file__).parent / "static" / "index.html"


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    """Serve the single-page UI. No build step, so nothing to break on deploy."""
    return FileResponse(INDEX)


@app.get("/health")
async def health() -> dict[str, object]:
    """Liveness probe. Also reports whether the LLM path is wired up."""
    return {
        "status": "ok",
        "environment": settings.environment,
        "llm_enabled": settings.llm_enabled,
        "model": settings.model if settings.llm_enabled else None,
    }


@app.post("/api/analyze", response_model=AnalysisResult)
async def analyze(request: AnalysisRequest) -> AnalysisResult:
    """Score a request through the rule engine, enriched by Claude when available."""
    return await engine.analyze(request)
