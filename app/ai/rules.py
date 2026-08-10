"""Deterministic rule engine.

This is the floor the service never drops below: no network, no API key, no
latency budget. Rules are plain data plus a predicate, so a topic-specific rule
set is a list literal rather than a new subclass.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from app.ai.schemas import Action, AnalysisRequest, AnalysisResult, Finding, RiskLevel

Predicate = Callable[[AnalysisRequest], bool]


@dataclass(frozen=True)
class Rule:
    code: str
    title: str
    weight: float
    predicate: Predicate
    detail: str = ""
    actions: tuple[str, ...] = ()


def keyword_rule(
    code: str,
    title: str,
    weight: float,
    keywords: tuple[str, ...],
    detail: str = "",
    actions: tuple[str, ...] = (),
) -> Rule:
    """Build a rule that fires when any keyword appears in the request text."""
    pattern = re.compile("|".join(re.escape(k) for k in keywords), re.IGNORECASE)

    def predicate(request: AnalysisRequest) -> bool:
        return bool(request.text) and bool(pattern.search(request.text))

    return Rule(
        code=code,
        title=title,
        weight=weight,
        predicate=predicate,
        detail=detail,
        actions=actions,
    )


def signal_rule(
    code: str,
    title: str,
    weight: float,
    key: str,
    expected: object,
    detail: str = "",
    actions: tuple[str, ...] = (),
) -> Rule:
    """Build a rule that fires when a structured signal equals `expected`."""

    def predicate(request: AnalysisRequest) -> bool:
        return request.signals.get(key) == expected

    return Rule(
        code=code,
        title=title,
        weight=weight,
        predicate=predicate,
        detail=detail,
        actions=actions,
    )


@dataclass
class RuleEngine:
    """Evaluates a rule set and turns matches into a scored result."""

    rules: list[Rule] = field(default_factory=list)
    # Score is capped at 100; weights are additive before the cap.
    cap: float = 100.0

    def evaluate(self, request: AnalysisRequest) -> AnalysisResult:
        matched = [rule for rule in self.rules if rule.predicate(request)]
        score = min(sum(rule.weight for rule in matched), self.cap)
        level = RiskLevel.from_score(score)

        findings = [
            Finding(
                code=rule.code,
                title=rule.title,
                detail=rule.detail,
                weight=rule.weight,
                source="rule",
            )
            for rule in matched
        ]

        # Preserve rule order and drop duplicates, so a step suggested by two
        # rules is shown once.
        seen: set[str] = set()
        actions: list[Action] = []
        for rule in matched:
            for instruction in rule.actions:
                if instruction in seen:
                    continue
                seen.add(instruction)
                actions.append(
                    Action(
                        order=len(actions) + 1,
                        instruction=instruction,
                        urgency="now" if rule.weight >= 30 else "soon",
                    )
                )

        return AnalysisResult(
            score=score,
            level=level,
            summary=self._summarize(level, len(matched)),
            findings=findings,
            actions=actions,
            engine="rules-only",
        )

    @staticmethod
    def _summarize(level: RiskLevel, match_count: int) -> str:
        if match_count == 0:
            return "탐지된 위험 신호가 없습니다."
        return f"위험도 {level.value} — {match_count}건의 위험 신호가 탐지되었습니다."
