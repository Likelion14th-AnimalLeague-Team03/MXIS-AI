# MXIS AI Care Model

MXIS Smart Charm MVP를 위한 럭셔리 가방 AI 케어 판단 엔진입니다.

이 저장소는 MXIS AI Care Model v1의 첫 번째 구현 기준을 담고 있습니다.

```text
SensorReading[]
-> Feature Extractor
-> Rule Evaluator
-> AI Care Summary
-> Frontend
```

이 모델은 손상 확률을 예측하지 않습니다. 온도, 습도, IMU 기반 움직임 데이터를 바탕으로 소재별 예방 관리 상태와 사용자에게 보여줄 케어 정보를 생성합니다.

OpenAI는 선택적으로 사용자-facing 문구 생성을 위해 사용할 수 있습니다. 단, 판단의 기준은 항상 deterministic Rule Evaluator 결과입니다.

## 현재 범위

지원 소재:

- `coated_cowhide`
- `natural_leather`
- `suede`
- `canvas`

지원 센서 입력:

- 온도
- 상대습도
- window 단위 `maxShock`
- window 단위 `motionCount`

중요한 MVP 제약:

- UV/light는 현재 센서로 직접 측정하지 않습니다.
- IMU 값은 손상 기준이 아니라 움직임/사용 노출 proxy입니다.
- 센서 데이터만으로 손상, 곰팡이, 갈라짐을 확정하지 않습니다.

## 폴더 구조

```text
.
├── api/                 # OpenAPI 계약
├── backend/             # Spring Boot 이식 가이드와 DTO 예시
├── data/                # Knowledge Base, rule spec, schema
├── docs/                # 설계 문서
├── examples/            # 요청/응답 예시
├── prototype/           # 실행 가능한 Python prototype
└── tests/fixtures/      # 검증 fixture와 synthetic dataset
```

## Prototype API 실행

```bash
python3 prototype/mxis_ai_api_server.py --host 127.0.0.1 --port 8765
```

실행 후 확인:

```text
http://127.0.0.1:8765/
http://127.0.0.1:8765/ai/demo-care-summary
```

샘플 센서 데이터로 POST 테스트:

```bash
curl -X POST http://127.0.0.1:8765/ai/care-summary \
  -H "Content-Type: application/json" \
  --data @examples/care-summary.request.json
```

위 요청은 `llm.enabled=false`인 기본 fallback 테스트입니다.

## OpenAI 설명 생성 사용

OpenAI를 사용하면 프론트 화면별 자연어 설명을 생성할 수 있습니다.

```bash
OPENAI_API_KEY=sk-... \
MXIS_USE_OPENAI=true \
OPENAI_MODEL=gpt-5-mini \
OPENAI_TIMEOUT_SECONDS=45 \
python3 prototype/mxis_ai_api_server.py --host 127.0.0.1 --port 8765
```

요청 body에서 개별적으로 켤 수도 있습니다.

```json
{
  "llm": {
    "enabled": true,
    "model": "gpt-5-mini",
    "locale": "ko-KR",
    "timeoutSeconds": 45
  }
}
```

OpenAI가 꺼져 있거나, API key가 없거나, 생성 결과 검증에 실패하면 deterministic fallback copy가 자동으로 반환됩니다.

OpenAI 설정 상태 확인:

```bash
curl http://127.0.0.1:8765/ai/openai-status
```

주의: `examples/care-summary.request.json`은 기본값이 `"enabled": false`입니다. 이 파일 그대로 테스트하면 OpenAI를 호출하지 않습니다. OpenAI를 테스트하려면 request body의 `llm.enabled`를 `true`로 바꾸거나, `llm` 블록을 제거하고 `MXIS_USE_OPENAI=true` 환경변수로 켜면 됩니다.

OpenAI 테스트용 요청:

```bash
curl -X POST http://127.0.0.1:8765/ai/care-summary \
  -H "Content-Type: application/json" \
  --data @examples/care-summary.openai-request.json
```

macOS에서 SSL 인증서 오류가 나는 경우:

```text
certificate verify failed: unable to get local issuer certificate
```

아래 중 하나로 해결할 수 있습니다.

권장 방법:

```bash
python3 -m pip install certifi
```

또는 `certifi` 경로를 명시합니다.

```bash
export SSL_CERT_FILE=$(python3 -m certifi)
```

특정 CA bundle을 쓰고 싶다면:

```bash
export OPENAI_CA_BUNDLE=/path/to/cacert.pem
```

로컬 임시 테스트에서만 TLS 검증을 끄려면:

```bash
export OPENAI_SKIP_TLS_VERIFY=true
```

`OPENAI_SKIP_TLS_VERIFY=true`는 개발 테스트 외에는 사용하지 않는 것을 권장합니다.

## 검증

```bash
python3 prototype/mxis_feature_extractor.py \
  --validate tests/fixtures/feature-extractor-cases.json \
  --pretty

python3 prototype/mxis_rule_evaluator.py \
  --validate tests/fixtures/rule-evaluator-cases.json \
  --pretty

python3 prototype/mxis_synthetic_dataset_generator.py --pretty
```

현재 기대 결과:

- Feature Extractor: `4/4`
- Rule Evaluator: `11/11`
- Synthetic Dataset: `14/14`

## API 계약

참고 문서:

- [api/openapi.yaml](api/openapi.yaml)
- [docs/07-api-endpoint.md](docs/07-api-endpoint.md)

핵심 endpoint:

```http
POST /ai/care-summary
```

응답의 주요 블록:

```text
aiCareSummary
├── dataSufficiency
├── productCondition
├── stressLabels
├── careDecision
├── explanation
├── llmCopy
├── copyGeneration
├── reservationCta
├── evidence
└── debug
```

프론트는 우선 다음 필드를 연결하면 됩니다.

- `aiCareSummary.productCondition`
- `aiCareSummary.stressLabels`
- `aiCareSummary.careDecision`
- `aiCareSummary.explanation`
- `aiCareSummary.llmCopy`
- `aiCareSummary.reservationCta`

## 백엔드 이식

백엔드 작업은 아래 문서부터 보면 됩니다.

- [backend/spring-boot-integration.md](backend/spring-boot-integration.md)
- [backend/MxisAiDtoSketch.java](backend/MxisAiDtoSketch.java)

권장 구현 순서:

1. `backend/MxisAiDtoSketch.java`를 기반으로 DTO 정의
2. `prototype/mxis_feature_extractor.py`를 `FeatureExtractorService`로 이식
3. `prototype/mxis_rule_evaluator.py`를 `RuleEvaluatorService`로 이식
4. `prototype/mxis_ai_api_server.py`의 응답 조립 로직을 `AiCareSummaryComposer`로 이식
5. `prototype/mxis_openai_explanation.py`의 OpenAI copy generation 로직을 선택적으로 이식
6. `POST /ai/care-summary` controller 구현
7. `tests/fixtures/*.json`을 Java unit test fixture로 전환

## 문서 읽는 순서

1. [Knowledge Base](docs/01-knowledge-base.md)
2. [Feature Extractor](docs/02-feature-extractor.md)
3. [Rule Evaluator](docs/03-rule-evaluator.md)
4. [AI Output Contract](docs/04-ai-output-contract.md)
5. [Weak Supervision](docs/05-weak-supervision.md)
6. [LLM Explanation](docs/06-llm-explanation.md)
7. [API Endpoint](docs/07-api-endpoint.md)

## 제품 안전 정책

출력하면 안 되는 것:

- 손상 확률
- 센서값만으로 확정한 손상 판정
- 센서값만으로 확정한 곰팡이 발생 판정
- 수리비
- 보증 관련 판단
- 정품/가품 판단

출력 가능한 것:

- 예방적 exposure label
- 관리 행동 추천
- 사용자 증상 또는 hard trigger 기반 점검 권장

## 현재 상태

현재 구현된 범위:

- SensorReading 기반 feature 추출
- 소재별 rule 기반 care 판단
- 프론트 전달용 `aiCareSummary` 생성
- OpenAI 기반 화면별 설명 생성 구조
- OpenAI 실패 시 fallback copy 자동 대체
- Spring Boot 백엔드 이식 가이드
- OpenAPI 계약
- 검증 fixture와 synthetic dataset
