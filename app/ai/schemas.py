"""Contracts shared by the rule engine and the LLM adapter.

The shape is built around one claim: for voice phishing, detection is not the
bottleneck — intervention is. A victim mid-call has already been persuaded, so a
bare risk score reads as one more untrusted voice. Every finding therefore
carries a `rebuttal`: the specific reason the thing the caller said is false.
That is what the user is shown, and the score is secondary.

`stage` splits the two products hiding in one service — talking someone out of a
transfer that has not happened yet, versus the first minutes after one has.
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


class Stage(str, Enum):
    """Where the user is relative to the moment money moves."""

    # Still talking, or just hung up. Nothing transferred yet.
    ONGOING = "ongoing"
    # Money already left the account. Minutes matter; the advice changes entirely.
    AFTER_TRANSFER = "after_transfer"
    UNKNOWN = "unknown"


class AnalysisRequest(BaseModel):
    """One unit of work for the AI layer."""

    text: str = Field(
        default="",
        max_length=20_000,
        description="Call transcript, message text, or the user's own account of it.",
    )
    signals: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured features the rule engine can match on.",
    )
    stage: Stage = Field(
        default=Stage.UNKNOWN,
        description="Whether a transfer has already happened.",
    )
    locale: str = Field(default="ko", description="Response language, BCP-47-ish.")


class Finding(BaseModel):
    """A single piece of evidence contributing to the score."""

    code: str = Field(description="Stable identifier, e.g. 'impersonation.authority'.")
    title: str
    detail: str = ""
    rebuttal: str = Field(
        default="",
        description=(
            "Why the caller's claim is false, stated so the user can check it "
            "themselves. This is the field the UI leads with."
        ),
    )
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
    stage: Stage = Stage.UNKNOWN
    findings: list[Finding] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)
    # Which path produced this result — surfaced to the UI so a degraded
    # response is never presented as a full-strength one.
    engine: Literal["hybrid", "rules-only", "llm-only"] = "rules-only"
    degraded: bool = Field(
        default=False,
        description="True when the LLM was expected but unavailable.",
    )
