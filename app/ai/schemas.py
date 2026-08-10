"""Contracts shared by the rule engine and the LLM adapter.

These are deliberately domain-neutral: an `AnalysisRequest` carries free text plus
arbitrary structured signals, and an `AnalysisResult` carries a risk score, a
label, the reasons behind it, and recommended actions. Any of the challenge's
candidate topics (fraud detection, policy-loan matching, growth scoring) maps
onto this shape by supplying its own rule set and its own prompt.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @classmethod
    def from_score(cls, score: float) -> "RiskLevel":
        if score >= 80:
            return cls.CRITICAL
        if score >= 60:
            return cls.HIGH
        if score >= 30:
            return cls.MEDIUM
        return cls.LOW


class AnalysisRequest(BaseModel):
    """One unit of work for the AI layer."""

    text: str = Field(
        default="",
        max_length=20_000,
        description="Free-form text to analyse (transcript, message, filing, ...).",
    )
    signals: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured features the rule engine can match on.",
    )
    locale: str = Field(default="ko", description="Response language, BCP-47-ish.")


class Finding(BaseModel):
    """A single piece of evidence contributing to the score."""

    code: str = Field(description="Stable identifier, e.g. 'impersonation.authority'.")
    title: str
    detail: str = ""
    weight: float = Field(default=0.0, description="Points contributed to the score.")
    source: Literal["rule", "llm"] = "rule"


class Action(BaseModel):
    """A recommended next step for the end user."""

    order: int
    instruction: str
    urgency: Literal["now", "soon", "later"] = "soon"


class AnalysisResult(BaseModel):
    score: float = Field(ge=0, le=100)
    level: RiskLevel
    summary: str
    findings: list[Finding] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)
    # Which path produced this result — surfaced to the UI so a degraded
    # response is never presented as a full-strength one.
    engine: Literal["hybrid", "rules-only", "llm-only"] = "rules-only"
    degraded: bool = Field(
        default=False,
        description="True when the LLM was expected but unavailable.",
    )
