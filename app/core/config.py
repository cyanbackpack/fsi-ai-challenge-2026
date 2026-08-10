"""Application settings, loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

# Claude Opus 5. Kept as a constant so the model choice lives in exactly one place.
DEFAULT_MODEL = "claude-opus-5"


@dataclass(frozen=True)
class Settings:
    app_name: str = "FSI AI Challenge 2026 MVP"
    environment: str = "development"

    # AI layer
    anthropic_api_key: str | None = None
    model: str = DEFAULT_MODEL
    # low | medium | high | xhigh | max — controls thinking depth and token spend.
    effort: str = "high"
    # Thinking is on by default on Claude Opus 5 and max_tokens caps thinking +
    # response text together, so this needs headroom beyond the visible answer.
    max_tokens: int = 8192
    # Wall-clock ceiling for a single Claude call, in seconds. When exceeded the
    # engine falls back to the rule engine rather than leaving a request hanging.
    llm_timeout_seconds: float = 30.0

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        environment=os.getenv("APP_ENV", "development"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        model=os.getenv("CLAUDE_MODEL", DEFAULT_MODEL),
        effort=os.getenv("CLAUDE_EFFORT", "high"),
        max_tokens=int(os.getenv("CLAUDE_MAX_TOKENS", "8192")),
        llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "30")),
    )
