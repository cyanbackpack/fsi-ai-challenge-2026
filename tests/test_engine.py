import pytest

from app.ai.client import LLMAction, LLMAnalysis, LLMFinding
from app.ai.engine import HybridEngine
from app.ai.rulesets import build_engine
from app.ai.schemas import AnalysisRequest, RiskLevel


class StubLLM:
    """Stands in for ClaudeClient so tests never touch the network."""

    def __init__(self, result: LLMAnalysis | None, available: bool = True) -> None:
        self._result = result
        self.available = available

    async def analyze(self, request, context=""):  # noqa: ANN001, ARG002
        return self._result


@pytest.mark.asyncio
async def test_rules_only_when_llm_unavailable():
    engine = HybridEngine(build_engine(), StubLLM(None, available=False))
    result = await engine.analyze(AnalysisRequest(text="지금 당장 OTP 알려주세요"))

    assert result.engine == "rules-only"
    assert result.degraded is False
    assert {f.code for f in result.findings} == {"pressure.urgency", "request.credentials"}
    assert result.score == 60
    assert result.level is RiskLevel.HIGH


@pytest.mark.asyncio
async def test_llm_failure_degrades_to_rules():
    engine = HybridEngine(build_engine(), StubLLM(None, available=True))
    result = await engine.analyze(AnalysisRequest(text="지금 당장 송금하세요"))

    assert result.engine == "rules-only"
    assert result.degraded is True


@pytest.mark.asyncio
async def test_llm_may_raise_score_but_not_lower_it():
    llm = StubLLM(
        LLMAnalysis(
            score=10,  # below the rule floor — must be ignored
            summary="모델 요약",
            findings=[LLMFinding(code="tone.coercive", title="강압적 어조", weight=5)],
            actions=[LLMAction(instruction="가족에게 알리세요", urgency="soon")],
        )
    )
    engine = HybridEngine(build_engine(), llm)
    result = await engine.analyze(AnalysisRequest(text="지금 당장 OTP 알려주세요"))

    assert result.engine == "hybrid"
    assert result.score == 60, "the rule floor must survive a lower model score"
    assert result.summary == "모델 요약"
    assert "tone.coercive" in {f.code for f in result.findings}
    assert "가족에게 알리세요" in {a.instruction for a in result.actions}


@pytest.mark.asyncio
async def test_llm_raises_score_above_rule_floor():
    llm = StubLLM(LLMAnalysis(score=95, summary="심각", findings=[], actions=[]))
    engine = HybridEngine(build_engine(), llm)
    result = await engine.analyze(AnalysisRequest(text="지금 당장 확인하세요"))

    assert result.score == 95
    assert result.level is RiskLevel.CRITICAL


@pytest.mark.asyncio
async def test_clean_input_scores_zero():
    engine = HybridEngine(build_engine(), StubLLM(None, available=False))
    result = await engine.analyze(AnalysisRequest(text="안녕하세요, 잔액 조회하고 싶습니다."))

    assert result.score == 0
    assert result.level is RiskLevel.LOW
    assert result.findings == []


@pytest.mark.asyncio
async def test_signal_rule_fires_without_text():
    engine = HybridEngine(build_engine(), StubLLM(None, available=False))
    result = await engine.analyze(AnalysisRequest(signals={"channel_verified": False}))

    assert {f.code for f in result.findings} == {"channel.unverified"}
    assert result.score == 15
