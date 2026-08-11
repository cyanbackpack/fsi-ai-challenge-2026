import pytest

from app.ai.client import LLMAction, LLMAnalysis, LLMFinding
from app.ai.engine import HybridEngine
from app.ai.rulesets import build_engine
from app.ai.schemas import AnalysisRequest, RiskLevel, Stage


class StubLLM:
    """Stands in for ClaudeClient so tests never touch the network."""

    def __init__(self, result: LLMAnalysis | None, available: bool = True) -> None:
        self._result = result
        self.available = available
        self.last_context: str | None = None

    async def analyze(self, request, context=""):  # noqa: ANN001, ARG002
        self.last_context = context
        return self._result


def rules_only() -> HybridEngine:
    return HybridEngine(build_engine(), StubLLM(None, available=False))


# --- rule engine behaviour ---------------------------------------------------


@pytest.mark.asyncio
async def test_decisive_signal_dominates_score():
    result = await rules_only().analyze(
        AnalysisRequest(text="안전계좌로 지금 당장 이체하셔야 합니다")
    )

    codes = {f.code for f in result.findings}
    assert "transfer.safe_account" in codes
    assert result.level is RiskLevel.CRITICAL


@pytest.mark.asyncio
async def test_every_finding_carries_a_rebuttal():
    result = await rules_only().analyze(
        AnalysisRequest(text="검찰인데 안전계좌로 이체하고 아무에게도 말하지 마세요")
    )

    assert result.findings, "expected the sample to trip several rules"
    for finding in result.findings:
        assert finding.rebuttal.strip(), f"{finding.code} has no rebuttal"


@pytest.mark.asyncio
async def test_actions_are_ordered_by_rule_weight():
    result = await rules_only().analyze(
        AnalysisRequest(text="검찰입니다. 안전계좌로 이체하세요. 지금 당장.")
    )

    assert result.actions[0].instruction.startswith("절대 이체하지"), (
        "the heaviest rule's action must come first"
    )
    assert [a.order for a in result.actions] == list(
        range(1, len(result.actions) + 1)
    )


@pytest.mark.asyncio
async def test_clean_input_scores_zero():
    result = await rules_only().analyze(
        AnalysisRequest(text="안녕하세요, 잔액 조회하고 싶습니다.")
    )

    assert result.score == 0
    assert result.level is RiskLevel.LOW
    assert result.findings == []


@pytest.mark.asyncio
async def test_signal_rule_fires_without_text():
    result = await rules_only().analyze(
        AnalysisRequest(signals={"channel_verified": False})
    )

    assert {f.code for f in result.findings} == {"channel.unverified"}
    assert result.score == 15


# --- stage handling ----------------------------------------------------------


@pytest.mark.asyncio
async def test_after_transfer_forces_critical_and_emergency_steps():
    result = await rules_only().analyze(
        AnalysisRequest(text="송금했습니다", stage=Stage.AFTER_TRANSFER)
    )

    assert result.level is RiskLevel.CRITICAL
    assert result.stage is Stage.AFTER_TRANSFER
    assert "지급정지" in result.actions[0].instruction
    assert all(a.urgency == "now" for a in result.actions)


@pytest.mark.asyncio
async def test_post_transfer_rule_stays_dormant_before_a_transfer():
    result = await rules_only().analyze(
        AnalysisRequest(text="송금했습니다", stage=Stage.ONGOING)
    )

    assert "stage.after_transfer" not in {f.code for f in result.findings}


# --- arbitration between the rule engine and the model -----------------------


@pytest.mark.asyncio
async def test_llm_failure_degrades_to_rules():
    engine = HybridEngine(build_engine(), StubLLM(None, available=True))
    result = await engine.analyze(AnalysisRequest(text="안전계좌로 이체하세요"))

    assert result.engine == "rules-only"
    assert result.degraded is True


@pytest.mark.asyncio
async def test_missing_key_is_not_reported_as_degraded():
    result = await rules_only().analyze(AnalysisRequest(text="안전계좌로 이체하세요"))

    assert result.engine == "rules-only"
    assert result.degraded is False


@pytest.mark.asyncio
async def test_llm_may_raise_score_but_not_lower_it():
    llm = StubLLM(
        LLMAnalysis(
            score=10,  # below the rule floor — must be ignored
            summary="모델 요약",
            findings=[
                LLMFinding(
                    code="story.inconsistent",
                    title="진술 모순",
                    rebuttal="앞뒤 설명이 어긋납니다.",
                    weight=5,
                )
            ],
            actions=[LLMAction(instruction="가족에게 알리세요", urgency="soon")],
        )
    )
    engine = HybridEngine(build_engine(), llm)
    result = await engine.analyze(AnalysisRequest(text="안전계좌로 이체하세요"))

    assert result.engine == "hybrid"
    assert result.score == 85, "the rule floor must survive a lower model score"
    assert result.summary == "모델 요약"
    assert "story.inconsistent" in {f.code for f in result.findings}
    assert "가족에게 알리세요" in {a.instruction for a in result.actions}


@pytest.mark.asyncio
async def test_rule_findings_are_passed_to_the_model_as_context():
    llm = StubLLM(LLMAnalysis(score=0, summary="", findings=[], actions=[]))
    engine = HybridEngine(build_engine(), llm)
    await engine.analyze(AnalysisRequest(text="안전계좌로 이체하세요"))

    assert "transfer.safe_account" in (llm.last_context or "")


@pytest.mark.asyncio
async def test_model_cannot_displace_emergency_actions():
    llm = StubLLM(
        LLMAnalysis(
            score=100,
            summary="긴급",
            findings=[],
            actions=[LLMAction(instruction="침착하세요", urgency="soon")],
        )
    )
    engine = HybridEngine(build_engine(), llm)
    result = await engine.analyze(
        AnalysisRequest(text="송금했습니다", stage=Stage.AFTER_TRANSFER)
    )

    assert "지급정지" in result.actions[0].instruction
    assert [a.order for a in result.actions] == list(range(1, len(result.actions) + 1))
