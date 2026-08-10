# API 명세 (기능 명세서 작성용)

주제 미정 상태의 기반 API입니다. 도메인 엔드포인트는 주제 확정 후 추가됩니다.

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

입력을 룰 엔진으로 채점하고, LLM 사용 가능 시 결과를 보강해 반환합니다.

**요청 본문**

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `text` | string | 아니오 | 분석 대상 텍스트. 최대 20,000자 |
| `signals` | object | 아니오 | 룰이 매칭할 구조화 신호 (키-값) |
| `locale` | string | 아니오 | 응답 언어. 기본 `"ko"` |

**응답 200**

| 필드 | 타입 | 설명 |
|---|---|---|
| `score` | number | 0~100 위험 점수 |
| `level` | enum | `low` (0–29) / `medium` (30–59) / `high` (60–79) / `critical` (80–100) |
| `summary` | string | 요약 설명 |
| `findings[]` | array | 점수에 기여한 근거 목록 |
| `findings[].code` | string | 안정적 식별자 (예: `request.credentials`) |
| `findings[].title` | string | 한 줄 제목 |
| `findings[].detail` | string | 부연 설명 |
| `findings[].weight` | number | 기여 점수 |
| `findings[].source` | enum | `rule` / `llm` — 근거의 출처 |
| `actions[]` | array | 권장 대응 행동 (순서대로) |
| `actions[].order` | integer | 표시 순서 |
| `actions[].instruction` | string | 구체적 행동 지시 |
| `actions[].urgency` | enum | `now` / `soon` / `later` |
| `engine` | enum | `hybrid` / `rules-only` / `llm-only` |
| `degraded` | boolean | LLM을 기대했으나 사용 불가였는지 여부 |

**응답 422** — 입력 검증 실패 (예: `text` 20,000자 초과)

### 동작 표

| 상황 | `engine` | `degraded` | 결과 |
|---|---|---|---|
| API 키 없음 | `rules-only` | `false` | 룰 점수 그대로 (정상 운영 모드) |
| LLM 호출 실패·거부 | `rules-only` | `true` | 룰 점수 그대로 (성능 저하 표시) |
| LLM 정상 응답 | `hybrid` | `false` | 룰 점수를 하한으로 병합 |

`degraded: true`인 응답은 UI에서 "간이 분석 결과"임을 사용자에게 표시할 것.
