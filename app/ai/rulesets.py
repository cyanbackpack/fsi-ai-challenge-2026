"""Voice-phishing rule set.

Each rule pairs a detectable pattern with the reason the caller's claim is false.
The rebuttal is written to be *checkable by the user without trusting us* — "the
number they gave you and the official number differ, dial the official one" beats
"our model scored this 87". A victim mid-call discounts assertions; they can
still verify a fact.

Rules are ordered by how decisive they are, not alphabetically.

Hotline numbers and the post-transfer procedure were verified 2026-08-11 against
금융위원회 (fsc.go.kr) and 은행연합회 소비자포털 (portal.kfb.or.kr). Re-check before
submission — wrong emergency guidance is worse than none.
"""

from __future__ import annotations

from app.ai.rules import Rule, RuleEngine, keyword_rule, signal_rule, stage_rule
from app.ai.schemas import Stage

CONTACTS = {
    "police": "112",  # 경찰청 — 보이스피싱 피해 신고 (통합신고대응센터)
    "fss": "1332",  # 금융감독원 — 상담·문의
}


# --- Decisive signals ---------------------------------------------------------
# These have no legitimate counterpart, so any one of them alone must reach
# CRITICAL (>= 80). Weights are set for that, not scaled against each other.

DECISIVE: list[Rule] = [
    keyword_rule(
        code="transfer.safe_account",
        title="'안전계좌' 이체 요구",
        weight=85,
        keywords=("안전계좌", "안전 계좌", "국가안전계좌", "보호계좌", "임시계좌"),
        detail="자금을 별도 계좌로 옮기라고 요구하고 있습니다.",
        rebuttal=(
            "'안전계좌'라는 제도는 존재하지 않습니다. 검찰·경찰·금융감독원 어디에도 "
            "국민의 돈을 대신 보관하는 계좌는 없습니다. 이 말이 나왔다면 100% 사기입니다."
        ),
        actions=("절대 이체하지 마시고 지금 통화를 끊으세요.",),
    ),
    keyword_rule(
        code="app.remote_control",
        title="원격제어 앱 설치 유도",
        weight=80,
        # Phrase-level, not bare "원격" — these rules score CRITICAL on their own,
        # so a benign "원격근무" must not trip them.
        keywords=(
            "원격제어",
            "원격 제어",
            "원격조종",
            "원격 조종",
            "원격지원",
            "팀뷰어",
            "teamviewer",
            "애니데스크",
            "anydesk",
            ".apk",
        ),
        detail="휴대폰을 원격으로 조작할 수 있는 앱 설치를 유도하고 있습니다.",
        rebuttal=(
            "정상적인 금융거래나 수사 절차에서 원격제어 앱을 설치하라고 요구하는 "
            "경우는 없습니다. 이 앱이 설치되면 상대가 당신 몰래 계좌 이체를 실행할 수 "
            "있습니다."
        ),
        actions=(
            "설치한 앱이 있다면 즉시 삭제하고 휴대폰을 비행기모드로 전환하세요.",
        ),
    ),
    keyword_rule(
        code="meeting.cash_handover",
        title="현금 인출 후 대면 전달 요구",
        weight=80,
        keywords=(
            "현금으로 찾아",
            "현금 인출해",
            "직접 만나",
            "만나서 전달",
            "수거",
            "직원이 방문",
            "집으로 찾아",
        ),
        detail="현금을 찾아 직접 전달하도록 요구하고 있습니다(대면편취형).",
        rebuttal=(
            "어떤 기관도 직원을 보내 현금을 수거하지 않습니다. 계좌 추적을 피하려고 "
            "현금 인출을 요구하는 것이며, 전달 즉시 회수가 사실상 불가능해집니다."
        ),
        actions=("절대 만나지 마시고 112에 즉시 신고하세요.",),
    ),
]


# --- Coercion --------------------------------------------------------------
# Isolation is the mechanism this whole service exists to break: it is why an
# outside warning does not land. Weighted just below decisive — on its own it is
# alarming but not conclusive, and paired with anything else it reaches CRITICAL.

COERCION: list[Rule] = [
    keyword_rule(
        code="secrecy.isolation",
        title="고립 유도 — 비밀 유지·통화 유지 요구",
        weight=45,
        keywords=(
            "아무에게도",
            "말하지 마",
            "비밀",
            "끊지 마",
            "끊지 말고",
            "혼자",
            "가족에게도",
        ),
        detail="주변에 알리지 못하게 하거나 통화를 계속 유지하도록 요구하고 있습니다.",
        rebuttal=(
            "이것이 가장 결정적인 신호입니다. 실제 수사기관은 가족에게 알리지 말라거나 "
            "통화를 끊지 말라고 요구하지 않습니다. 당신을 확인할 수 없는 상태로 "
            "묶어두려는 것이며, 사기가 아니라면 확인을 막을 이유가 없습니다."
        ),
        actions=("지금 통화를 끊고 가족이나 지인에게 상황을 그대로 말하세요.",),
    ),
]


# --- Impersonation patterns ---------------------------------------------------

IMPERSONATION: list[Rule] = [
    keyword_rule(
        code="impersonation.authority",
        title="수사·감독기관 사칭",
        weight=30,
        keywords=("검찰", "검사", "경찰", "수사관", "금융감독원", "국세청", "구속영장"),
        detail="수사기관이나 감독기관을 사칭해 신뢰를 얻으려 하고 있습니다.",
        rebuttal=(
            "수사기관은 전화로 사건을 통보하거나 계좌를 요구하지 않습니다. 공문·영장을 "
            "카카오톡이나 문자로 보내는 일도 없습니다. 지금 통화를 끊고 해당 기관 "
            "대표번호로 직접 걸어 사건 존재 여부를 확인하세요 — 진짜라면 확인이 됩니다."
        ),
        actions=("통화를 끊고 해당 기관 공식 대표번호로 직접 확인하세요.",),
    ),
    keyword_rule(
        code="impersonation.family",
        title="가족·지인 사칭 (메신저피싱)",
        weight=30,
        keywords=("엄마", "아빠", "폰이 고장", "액정", "새 번호", "카톡으로"),
        detail="가족을 사칭하며 새 번호나 메신저로 접근하고 있습니다.",
        rebuttal=(
            "번호가 바뀌었다며 돈을 요구하는 것은 메신저피싱의 전형입니다. 기존에 알던 "
            "번호로 직접 전화해 목소리를 확인하세요. 상대가 통화를 피하고 문자만 "
            "고집한다면 사칭입니다."
        ),
        actions=("원래 알던 번호로 직접 전화해 본인 확인을 하세요.",),
    ),
]


# --- Financial-instrument lures ----------------------------------------------

LURES: list[Rule] = [
    keyword_rule(
        code="loan.upfront_payment",
        title="대출 명목 선입금 요구",
        weight=40,
        keywords=("보증료", "선입금", "전산작업비", "공탁금", "예치금", "신용등급 상향"),
        detail="대출 실행을 조건으로 먼저 돈을 보내라고 요구하고 있습니다.",
        rebuttal=(
            "어떤 명목이든 대출을 받기 위해 먼저 돈을 보내는 절차는 존재하지 않으며, "
            "선입금 요구 자체가 대부업법 위반입니다. 신용등급을 돈으로 올릴 수도 없습니다."
        ),
        actions=("입금하지 마시고 해당 금융회사 대표번호로 직접 확인하세요.",),
    ),
    keyword_rule(
        code="loan.low_interest_switch",
        title="저금리 대환대출 미끼",
        weight=25,
        keywords=("저금리", "대환", "정부지원 대출", "특별자금", "한도 상향"),
        detail="파격적인 조건의 대출을 제안하고 있습니다.",
        rebuttal=(
            "전화나 문자로 먼저 접근해 저금리 대출을 권유하는 정식 금융회사는 없습니다. "
            "금융소비자 정보포털에서 해당 업체가 등록된 곳인지 먼저 확인하세요."
        ),
    ),
]


# --- Credential and pressure patterns ----------------------------------------

GENERAL: list[Rule] = [
    keyword_rule(
        code="credentials.request",
        title="인증정보 요구",
        weight=35,
        keywords=("비밀번호", "OTP", "인증번호", "보안카드", "공인인증", "카드번호"),
        detail="계좌 접근에 필요한 인증정보를 요구하고 있습니다.",
        rebuttal=(
            "금융기관과 수사기관 모두 어떤 상황에서도 비밀번호·OTP·보안카드 번호를 "
            "묻지 않습니다. 이 정보를 넘기는 순간 계좌가 즉시 비워질 수 있습니다."
        ),
        actions=("어떤 인증정보도 전달하지 마세요.",),
    ),
    keyword_rule(
        code="link.unknown_url",
        title="출처 불명 링크",
        weight=20,
        keywords=("bit.ly", "http://", "링크를 눌러", "클릭하세요", "설치하세요"),
        detail="확인되지 않은 링크나 앱 설치를 유도하고 있습니다.",
        rebuttal=(
            "링크로 설치되는 앱은 통화를 가로채 어디로 걸든 사기범에게 연결되게 만들 "
            "수 있습니다. 확인 전화조차 무력화되므로 절대 누르지 마세요."
        ),
    ),
    keyword_rule(
        code="pressure.urgency",
        title="시간 압박",
        weight=20,
        keywords=("지금 당장", "즉시", "오늘까지", "마감", "늦으면", "구속"),
        detail="판단할 시간을 주지 않으려 압박하고 있습니다.",
        rebuttal=(
            "정상적인 금융·법률 절차에 몇 분 안에 결정해야 하는 일은 없습니다. "
            "서두르게 만드는 것 자체가 확인할 틈을 주지 않으려는 수법입니다."
        ),
    ),
    signal_rule(
        code="channel.unverified",
        title="미확인 발신 채널",
        weight=15,
        key="channel_verified",
        expected=False,
        detail="발신자가 검증되지 않은 채널로 접근했습니다.",
        rebuttal="발신번호는 조작이 가능합니다. 표시된 번호를 신뢰하지 마세요.",
    ),
]


# --- Post-transfer emergency response ----------------------------------------
# Weight is maxed so this dominates the score and its actions sort to the top:
# once money has moved, nothing else on the page matters.

POST_TRANSFER: list[Rule] = [
    stage_rule(
        code="stage.after_transfer",
        title="송금 완료 — 긴급 지급정지 필요",
        weight=100,
        stage=Stage.AFTER_TRANSFER,
        detail="이미 자금이 이체된 상태입니다.",
        rebuttal=(
            "사기범이 돈을 인출하기 전에 계좌를 묶으면 돌려받을 수 있습니다. "
            "지급정지는 신고가 빠를수록 성공률이 높으므로 지금 바로 진행하세요."
        ),
        actions=(
            f"거래 은행 콜센터 또는 {CONTACTS['police']}에 전화해 지급정지를 요청하세요. "
            "긴급한 경우 전화만으로 신청할 수 있습니다.",
            "송금한 계좌번호, 금액, 시각을 메모해 두세요. 신고할 때 바로 필요합니다.",
            "경찰서에서 '사건사고사실확인원'을 발급받으세요. 피해구제 신청에 필요합니다.",
            "확인원과 신분증 사본을 가지고 은행 영업점에서 '피해구제 신청서'를 제출하세요.",
            f"절차가 헷갈리면 금융감독원 {CONTACTS['fss']}로 문의하세요.",
            "본인 명의로 몰래 개통된 휴대폰·계좌가 없는지 확인하세요.",
        ),
    ),
]


VOICE_PHISHING_RULES: list[Rule] = [
    *DECISIVE,
    *COERCION,
    *IMPERSONATION,
    *LURES,
    *GENERAL,
    *POST_TRANSFER,
]

_RULESETS = {"voice_phishing": VOICE_PHISHING_RULES}


def build_engine(topic: str = "voice_phishing") -> RuleEngine:
    """Return the rule engine for a topic. Unknown topics fall back to the default."""
    rules = _RULESETS.get(topic, VOICE_PHISHING_RULES)
    return RuleEngine(rules=list(rules))
