"""Rule sets, keyed by topic.

PLACEHOLDER — the competition topic is not yet chosen, so this ships with a
single generic set that exercises the plumbing end to end. Once the topic is
settled, replace `GENERIC_RULES` with the domain rule set (or add a second entry
and select it by name); nothing else in the AI layer needs to change.
"""

from __future__ import annotations

from app.ai.rules import Rule, RuleEngine, keyword_rule, signal_rule

GENERIC_RULES: list[Rule] = [
    keyword_rule(
        code="pressure.urgency",
        title="긴급성 압박 표현",
        weight=25,
        keywords=("지금 당장", "즉시", "빨리", "마감", "오늘까지"),
        detail="상대가 시간을 압박해 판단할 여유를 주지 않는 전형적인 패턴입니다.",
        actions=("통화를 끊고 공식 대표번호로 직접 확인하세요.",),
    ),
    keyword_rule(
        code="request.credentials",
        title="인증정보 요구",
        weight=35,
        keywords=("비밀번호", "OTP", "인증번호", "보안카드", "계좌번호"),
        detail="정상적인 금융기관은 전화나 문자로 인증정보를 요구하지 않습니다.",
        actions=("어떤 인증정보도 전달하지 마세요.",),
    ),
    keyword_rule(
        code="impersonation.authority",
        title="공공기관 사칭 정황",
        weight=30,
        keywords=("검찰", "경찰", "금융감독원", "국세청"),
        detail="수사기관·감독기관을 사칭해 신뢰를 얻으려는 시도로 보입니다.",
        actions=("해당 기관 대표번호로 사실 여부를 확인하세요.",),
    ),
    signal_rule(
        code="channel.unverified",
        title="미확인 발신 채널",
        weight=15,
        key="channel_verified",
        expected=False,
        detail="발신자가 검증되지 않은 채널로 접근했습니다.",
    ),
]


def build_engine(topic: str = "generic") -> RuleEngine:
    """Return the rule engine for a topic. Unknown topics fall back to generic."""
    rules = {"generic": GENERIC_RULES}.get(topic, GENERIC_RULES)
    return RuleEngine(rules=list(rules))
