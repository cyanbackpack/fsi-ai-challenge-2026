"""Structural guards on the rule set itself.

These enforce invariants the rule set documents in prose, so a later edit that
contradicts the design fails a test instead of quietly shipping.
"""

import pytest

from app.ai.rulesets import DECISIVE, VOICE_PHISHING_RULES, build_engine
from app.ai.schemas import AnalysisRequest, RiskLevel

CRITICAL_THRESHOLD = 80


def test_rule_codes_are_unique():
    codes = [rule.code for rule in VOICE_PHISHING_RULES]
    assert len(codes) == len(set(codes))


@pytest.mark.parametrize("rule", DECISIVE, ids=lambda r: r.code)
def test_decisive_rules_reach_critical_alone(rule):
    """A signal with no legitimate counterpart must not need corroboration."""
    assert rule.weight >= CRITICAL_THRESHOLD


@pytest.mark.parametrize("rule", VOICE_PHISHING_RULES, ids=lambda r: r.code)
def test_every_rule_explains_itself(rule):
    """A finding without a rebuttal is a bare assertion — the thing that fails."""
    assert rule.rebuttal.strip(), f"{rule.code} has no rebuttal"
    assert rule.title.strip()


# Text that must not be flagged. Each of these previously tripped a rule whose
# keywords were too loose.
BENIGN = [
    "원격근무 중이라 은행에 못 갔어요",
    "현금 인출 수수료가 얼마인가요?",
    "적금 만기가 오늘까지인데 자동 연장되나요?",
    "안녕하세요, 잔액 조회하고 싶습니다.",
]


@pytest.mark.parametrize("text", BENIGN)
def test_benign_text_does_not_reach_critical(text):
    result = build_engine().evaluate(AnalysisRequest(text=text))
    assert result.level is not RiskLevel.CRITICAL, (
        f"false positive on {text!r}: {[f.code for f in result.findings]}"
    )
