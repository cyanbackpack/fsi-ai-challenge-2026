"""Deterministic rule engine.

This is the floor the service never drops below: no network, no API key, no
latency budget. Rules are plain data plus a predicate, so a topic-specific rule
set is a list literal rather than a new subclass.

A rule carries a `rebuttal` alongside its weight because, for this domain, the
rebuttal is the product. The score orders the evidence; the rebuttal is what
actually reaches a person who has already been persuaded.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from app.ai.schemas import (
    Action,
    AnalysisRequest,
    AnalysisResult,
    Finding,
    RiskLevel,
    Stage,
)

Predicate = Callable[[AnalysisRequest], bool]


@dataclass(frozen=True)
class Rule:
    code: str
    title: str
    weight: float
    predicate: Predicate
    detail: str = ""
    rebuttal: str = ""
    actions: tuple[str, ...] = ()
    # Restrict the rule to one stage. None means it applies at every stage.
    stage: Stage | None = None


def _staged(predicate: Predicate, stage: Stage | None) -> Predicate:
    if stage is None:
        return predicate

    def wrapped(request: AnalysisRequest) -> bool:
        return request.stage is stage and predicate(request)

    return wrapped


def keyword_rule(
    code: str,
    title: str,
    weight: float,
    keywords: tuple[str, ...],
    detail: str = "",
    rebuttal: str = "",
    actions: tuple[str, ...] = (),
    stage: Stage | None = None,
) -> Rule:
    """Build a rule that fires when any keyword appears in the request text."""
    pattern = re.compile("|".join(re.escape(k) for k in keywords), re.IGNORECASE)

    def predicate(request: AnalysisRequest) -> bool:
        return bool(request.text) and bool(pattern.search(request.text))

    return Rule(
        code=code,
        title=title,
        weight=weight,
        predicate=_staged(predicate, stage),
        detail=detail,
        rebuttal=rebuttal,
        actions=actions,
        stage=stage,
    )


def signal_rule(
    code: str,
    title: str,
    weight: float,
    key: str,
    expected: object,
    detail: str = "",
    rebuttal: str = "",
    actions: tuple[str, ...] = (),
    stage: Stage | None = None,
) -> Rule:
    """Build a rule that fires when a structured signal equals `expected`."""

    def predicate(request: AnalysisRequest) -> bool:
        return request.signals.get(key) == expected

    return Rule(
        code=code,
        title=title,
        weight=weight,
        predicate=_staged(predicate, stage),
        detail=detail,
        rebuttal=rebuttal,
        actions=actions,
        stage=stage,
    )


def stage_rule(
    code: str,
    title: str,
    weight: float,
    stage: Stage,
    detail: str = "",
    rebuttal: str = "",
    actions: tuple[str, ...] = (),
) -> Rule:
    """Build a rule that fires on the stage alone, regardless of content."""
    return Rule(
        code=code,
        title=title,
        weight=weight,
        predicate=_staged(lambda _request: True, stage),
        detail=detail,
        rebuttal=rebuttal,
        actions=actions,
        stage=stage,
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
                rebuttal=rule.rebuttal,
                weight=rule.weight,
                source="rule",
            )
            for rule in matched
        ]

        # Heaviest rules first, so the most urgent step is action #1. Ties keep
        # rule-set order, which is authored deliberately.
        ordered = sorted(matched, key=lambda rule: -rule.weight)

        seen: set[str] = set()
        actions: list[Action] = []
        for rule in ordered:
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
            summary=self._summarize(request.stage, level, len(matched)),
            stage=request.stage,
            findings=findings,
            actions=actions,
            engine="rules-only",
        )

    @staticmethod
    def _summarize(stage: Stage, level: RiskLevel, match_count: int) -> str:
        if stage is Stage.AFTER_TRANSFER:
            return (
                "이미 송금이 이루어진 상황입니다. 지급정지는 시간이 지날수록 "
                "성공률이 떨어지니 아래 순서대로 즉시 진행하세요."
            )
        if match_count == 0:
            return "입력된 내용에서는 알려진 보이스피싱 수법이 탐지되지 않았습니다."
        return (
            f"위험도 {level.value} — 보이스피싱에서 반복적으로 확인되는 수법 "
            f"{match_count}가지가 탐지되었습니다. 아래 반박 근거를 직접 확인해 보세요."
        )
