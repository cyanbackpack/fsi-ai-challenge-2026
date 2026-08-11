"""Claude adapter.

Wraps the Anthropic SDK behind a narrow interface so the orchestrator can treat
"the LLM is unavailable" as an ordinary outcome rather than an exception path.
Every failure — missing key, timeout, rate limit, malformed output — surfaces as
`None`, and the caller falls back to the rule engine.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, Field

from app.ai.schemas import AnalysisRequest
from app.core.config import Settings

logger = logging.getLogger(__name__)


class LLMFinding(BaseModel):
    """A finding as the model is asked to return it."""

    code: str = Field(description="Short stable slug, e.g. 'urgency.pressure'.")
    title: str = Field(description="One-line label in the requested locale.")
    detail: str = Field(default="", description="Why this matters, 1-2 sentences.")
    rebuttal: str = Field(
        default="",
        description=(
            "The reason the caller's specific claim is false, phrased so the "
            "reader can verify it themselves rather than having to trust us."
        ),
    )
    weight: float = Field(
        default=0.0, ge=0, le=100, description="Points this contributes to the score."
    )


class LLMAction(BaseModel):
    instruction: str = Field(description="A concrete step the user should take.")
    urgency: Literal["now", "soon", "later"] = "soon"


class LLMAnalysis(BaseModel):
    """The structured output contract enforced on the model's response."""

    score: float = Field(ge=0, le=100, description="Overall risk score.")
    summary: str = Field(description="Two or three sentences in the requested locale.")
    findings: list[LLMFinding] = Field(default_factory=list)
    actions: list[LLMAction] = Field(default_factory=list)


SYSTEM_PROMPT = """\
You help someone who may be in the middle of a voice-phishing scam right now.

Assume the reader has already been persuaded by the caller. Telling them "this is \
a scam" does not work — to them you are one more stranger making a claim. What \
works is a fact they can check for themselves: that the procedure the caller \
described does not exist, that the official number differs from the one they were \
given, that no real institution asks for this. Put that in `rebuttal`, and write \
it as something they can verify, not as something they must take on faith.

A deterministic rule engine has already run and its findings are given to you. Do \
not restate them. Add what it missed — manipulation tactics specific to this \
conversation, internal contradictions in the caller's story, details that are \
implausible for the institution being claimed. If it missed nothing, return no \
findings; an empty list is a valid and useful answer.

Ground every finding in something actually present in the input. If the input is \
too thin to judge, say so in the summary and score low rather than filling the \
gap. A false alarm teaches this person to ignore the next warning.

When `stage` is `after_transfer`, the persuasion question is settled and speed is \
all that matters: keep the summary to one or two sentences and let the actions \
carry the weight.

Write every user-facing string in the language named by the request's locale. \
Keep the summary to two or three sentences and each action to one concrete step \
that can be taken immediately. Prefer plain words over financial or legal jargon — \
the reader may be elderly, distressed, or both.\
"""


class ClaudeClient:
    """Thin async wrapper around the Messages API."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = None

        if not settings.llm_enabled:
            logger.info("ANTHROPIC_API_KEY not set — running rules-only.")
            return

        try:
            from anthropic import AsyncAnthropic
        except ImportError:  # pragma: no cover - depends on install extras
            logger.warning("anthropic SDK not installed — running rules-only.")
            return

        self._client = AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.llm_timeout_seconds,
        )

    @property
    def available(self) -> bool:
        return self._client is not None

    async def analyze(
        self, request: AnalysisRequest, context: str = ""
    ) -> LLMAnalysis | None:
        """Return a structured analysis, or None if the model could not produce one."""
        if self._client is None:
            return None

        user_content = _build_user_message(request, context)

        try:
            response = await self._client.messages.parse(
                model=self._settings.model,
                max_tokens=self._settings.max_tokens,
                system=SYSTEM_PROMPT,
                output_format=LLMAnalysis,
                output_config={"effort": self._settings.effort},
                messages=[{"role": "user", "content": user_content}],
            )
        except Exception:
            # Any SDK-level failure (auth, rate limit, timeout, transport) is a
            # degraded response, not an outage — the caller falls back to rules.
            logger.exception("Claude call failed; falling back to the rule engine.")
            return None

        if response.stop_reason == "refusal":
            logger.warning("Claude declined the request; falling back to the rules.")
            return None

        return response.parsed_output


def _build_user_message(request: AnalysisRequest, context: str) -> str:
    parts = [f"locale: {request.locale}", f"stage: {request.stage.value}"]
    if context:
        parts.append(f"<deterministic_findings>\n{context}\n</deterministic_findings>")
    if request.signals:
        rendered = "\n".join(f"- {k}: {v}" for k, v in sorted(request.signals.items()))
        parts.append(f"<signals>\n{rendered}\n</signals>")
    parts.append(f"<input>\n{request.text}\n</input>")
    return "\n\n".join(parts)
