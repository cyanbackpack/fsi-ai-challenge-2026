# 2026 금융 AI Challenge — MVP

금융보안원 주최 **2026 금융 AI Challenge** 제출용 MVP 웹서비스의 기반 코드입니다.

> **현재 상태: 주제 미정.** 도메인 로직(룰셋·프롬프트·화면)은 주제 확정 후 붙입니다.
> 이 저장소에는 주제와 무관하게 재사용되는 **AI 레이어와 서버 골격**만 들어 있습니다.

## 아키텍처

```
요청 ─▶ RuleEngine (결정론적, 항상 실행)
          │  findings를 컨텍스트로 전달
          ▼
       ClaudeClient (선택적, 구조화 출력)
          │
          ▼
       HybridEngine — 병합 후 응답
```

**중재 규칙(arbitration policy)**

- 룰 엔진은 항상 실행되며 그 점수는 **하한선**입니다. LLM은 점수를 **올릴 수만** 있습니다.
- LLM 호출이 실패하면(키 없음·타임아웃·레이트리밋·거부·파싱 실패) 룰 결과를 그대로 반환하고
  응답에 `degraded: true`를 표시합니다. **서비스는 멈추지 않습니다.**
- `ANTHROPIC_API_KEY`가 없으면 룰 전용 모드로 동작하며, 이는 장애가 아니므로
  `degraded: false`입니다. (`engine` 필드로 구분 가능)

심사 기간(9/7~9/11) 중 API 장애나 크레딧 소진이 나도 서비스가 죽지 않도록 한 설계입니다.

### 모델 설정

- 모델: `claude-opus-5` (기본값, `CLAUDE_MODEL`로 변경 가능)
- 사고(thinking)는 Claude Opus 5에서 기본 활성화되며 `max_tokens`가 사고와 응답을 **함께** 제한하므로
  기본값을 8192로 두었습니다. 줄일 경우 응답 잘림에 유의하세요.
- 깊이/비용은 `CLAUDE_EFFORT` (`low`~`max`)로 조절합니다.
- 출력은 Pydantic 스키마(`LLMAnalysis`)로 강제되어 파싱 실패가 구조적으로 차단됩니다.

## 실행

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # 키 없이도 룰 전용으로 동작합니다
uvicorn app.main:app --reload
```

테스트:

```bash
pytest
```

## API

| 메서드 | 경로 | 설명 |
|---|---|---|
| `GET` | `/health` | 상태 확인. `llm_enabled`로 LLM 경로 활성 여부 확인 |
| `POST` | `/api/analyze` | 텍스트·신호를 분석해 위험 점수와 대응 행동을 반환 |
| `GET` | `/docs` | FastAPI 자동 생성 OpenAPI 문서 |

기능 명세서 작성용 상세 스펙은 [`docs/api-spec.md`](docs/api-spec.md)를 참고하세요.

### 요청 예시

```bash
curl -X POST localhost:8000/api/analyze \
  -H 'Content-Type: application/json' \
  -d '{"text":"지금 당장 OTP 알려주세요","signals":{"channel_verified":false}}'
```

## 디렉터리

```
app/
  core/config.py     환경변수 기반 설정
  ai/schemas.py      요청·응답 계약 (도메인 중립)
  ai/rules.py        결정론적 룰 엔진
  ai/rulesets.py     룰셋 — 주제 확정 시 이 파일을 교체
  ai/client.py       Claude 어댑터 (실패 시 None 반환)
  ai/engine.py       하이브리드 오케스트레이터 + 중재 규칙
  main.py            FastAPI 엔트리포인트
tests/               룰·중재·API 테스트
docs/api-spec.md     기능 명세서용 엔드포인트 정리
```

## 주제 확정 후 해야 할 일

1. `app/ai/rulesets.py`의 `GENERIC_RULES`를 도메인 룰셋으로 교체
2. `app/ai/client.py`의 `SYSTEM_PROMPT`를 도메인에 맞게 작성
3. 프론트엔드 추가 및 배포 (`render.yaml` 참고)
4. 데이터 출처를 이 README에 명시 (아래 섹션)

## 데이터 출처

현재 코드에 포함된 룰셋은 **공개된 보이스피싱 대응 요령을 참고해 직접 작성한 예시**이며,
외부 데이터셋을 포함하지 않습니다. 주제 확정 후 외부 데이터(공공데이터포털, 오픈뱅킹 API 등)를
사용할 경우 출처와 라이선스를 이 섹션에 반드시 명시합니다.

## 라이선스

의존성은 모두 허용적 라이선스(MIT/BSD/Apache-2.0)입니다: FastAPI, Uvicorn, Pydantic, anthropic SDK.
