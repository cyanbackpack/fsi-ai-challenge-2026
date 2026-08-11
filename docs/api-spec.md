# API 명세 (기능 명세서 작성용)

## GET /health

상태 확인 및 AI 경로 활성 여부 확인.

**응답 200**

| 필드 | 타입 | 설명 |
|---|---|---|
| `status` | string | 항상 `"ok"` |
| `environment` | string | `APP_ENV` 값 |
| `llm_enabled` | boolean | `ANTHROPIC_API_KEY` 설정 여부 |
| `model` | string \| null | 활성 모델명. 비활성 시 `null` |

## POST /api/analyze

통화·문자 내용을 분석해 **위험 점수, 반박 근거, 대응 행동**을 반환합니다.

**요청 본문**

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `text` | string | 아니오 | 통화 내용, 문자 원문, 또는 사용자의 진술. 최대 20,000자 |
| `signals` | object | 아니오 | 룰이 매칭할 구조화 신호 (예: `{"channel_verified": false}`) |
| `stage` | enum | 아니오 | `ongoing` / `after_transfer` / `unknown` (기본값) |
| `locale` | string | 아니오 | 응답 언어. 기본 `"ko"` |

**응답 200**

| 필드 | 타입 | 설명 |
|---|---|---|
| `score` | number | 0~100 위험 점수 |
| `level` | enum | `low` (0–29) / `medium` (30–59) / `high` (60–79) / `critical` (80–100) |
| `summary` | string | 요약 설명 |
| `stage` | enum | 요청의 `stage` 반영 |
| `findings[]` | array | 탐지된 수법 목록 |
| `findings[].code` | string | 안정적 식별자 (예: `transfer.safe_account`) |
| `findings[].title` | string | 한 줄 제목 |
| `findings[].detail` | string | 무엇이 탐지되었는지 |
| `findings[].rebuttal` | string | **핵심 필드.** 상대 주장이 거짓인 이유 — UI는 이것을 가장 크게 표시 |
| `findings[].weight` | number | 기여 점수 |
| `findings[].source` | enum | `rule` / `llm` |
| `actions[]` | array | 권장 대응 행동 (위험도 높은 순) |
| `actions[].order` | integer | 표시 순서 |
| `actions[].instruction` | string | 구체적 행동 지시 |
| `actions[].urgency` | enum | `now` / `soon` / `later` |
| `engine` | enum | `hybrid` / `rules-only` / `llm-only` |
| `degraded` | boolean | LLM을 기대했으나 사용 불가였는지 여부 |

**응답 422** — 입력 검증 실패 (`text` 20,000자 초과, 잘못된 `stage` 값 등)

### 동작 표

| 상황 | `engine` | `degraded` | 결과 |
|---|---|---|---|
| API 키 없음 | `rules-only` | `false` | 룰 점수 그대로 (정상 운영 모드) |
| LLM 호출 실패·거부 | `rules-only` | `true` | 룰 점수 그대로 (성능 저하 표시) |
| LLM 정상 응답 | `hybrid` | `false` | 룰 점수를 하한으로 병합 |

`degraded: true`인 응답은 UI에서 "간이 분석 결과"임을 사용자에게 표시할 것.

### 단계별 동작

| `stage` | 동작 |
|---|---|
| `ongoing` / `unknown` | 설득 해제 중심. 반박 근거를 크게, 확인 절차를 행동으로 제시 |
| `after_transfer` | 점수 100 고정, 요약을 짧게, 지급정지 절차가 `actions[0]`부터 순서대로 |

### 위험도 산정 규칙

- 룰 가중치를 합산하고 100에서 상한 처리합니다.
- **결정적 신호**(안전계좌 요구, 원격제어 앱, 대면 현금 수거)는 단독으로 `critical`에 도달합니다. 정상적인 대응물이 존재하지 않는 수법이기 때문입니다.
- LLM은 점수를 **올릴 수만** 있습니다. 룰 점수가 하한선입니다.
