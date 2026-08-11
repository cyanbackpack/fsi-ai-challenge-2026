"""Hybrid orchestrator: rule engine first, Claude second, merged deterministically.

Arbitration policy
------------------
The rule engine runs on every request and its score is a **floor**. Rules encode
obligations we can state precisely, so the LLM is allowed to raise a score or add
context but never to argue one away. If the LLM is unavailable the rule result is
returned unchanged, flagged `degraded` so the caller can say so in the UI.
"""

from __future__ import annotations

from app.ai.client import ClaudeClient, LLMAnalysis
from app.ai.rules import RuleEngine
from app.ai.schemas import Action, AnalysisRequest, AnalysisResult, Finding, RiskLevel


class HybridEngine:
    def __init__(self, rules: RuleEngine, llm: ClaudeClient) -> None:
        self._rules = rules
        self._llm = llm

    async def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        baseline = self._rules.evaluate(request)

        if not self._llm.available:
            baseline.degraded = False  # rules-only is the configured mode, not a fault
            return baseline

        analysis = await self._llm.analyze(request, context=_render(baseline.findings))
        if analysis is None:
            baseline.degraded = True
            return baseline

        return _merge(baseline, analysis)


def _render(findings: list[Finding]) -> str:
    if not findings:
        return "none"
    return "\n".join(f"- [{f.code}] {f.title} (weight {f.weight})" for f in findings)


def _next_order(actions: list[Action]) -> int:
    return max((a.order for a in actions), default=0) + 1


def _merge(baseline: AnalysisResult, analysis: LLMAnalysis) -> AnalysisResult:
    # Rules set the floor; the model may only raise the score.
    score = max(baseline.score, min(analysis.score, 100.0))

    findings = list(baseline.findings)
    known = {f.code for f in findings}
    for item in analysis.findings:
        if item.code in known:
            continue
        known.add(item.code)
        findings.append(
            Finding(
                code=item.code,
                title=item.title,
                detail=item.detail,
                rebuttal=item.rebuttal,
                weight=item.weight,
                source="llm",
            )
        )

    # Rule actions keep their positions — they are the vetted ones, and after a
    # transfer they are the emergency steps. Model suggestions append.
    actions = list(baseline.actions)
    seen = {a.instruction for a in actions}
    for item in analysis.actions:
        if item.instruction in seen:
            continue
        seen.add(item.instruction)
        actions.append(
            Action(
                order=_next_order(actions),
                instruction=item.instruction,
                urgency=item.urgency,
            )
        )

    return AnalysisResult(
        score=score,
        level=RiskLevel.from_score(score),
        summary=analysis.summary or baseline.summary,
        stage=baseline.stage,
        findings=findings,
        actions=actions,
        engine="hybrid",
        degraded=False,
    )
