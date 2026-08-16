# MXIS AI Endpoint Contract v0.1

작성일: 2026-08-17

상태: MVP Prototype

## 1. 목적

현재 Python prototype으로 구현된 MXIS AI 파이프라인을 프론트가 호출할 수 있는 API 형태로 제공한다.

```text
POST /ai/care-summary
-> Feature Extractor
-> Rule Evaluator
-> AI Output Composer
-> OpenAI Explanation or deterministic fallback
-> aiCareSummary
```

이 엔드포인트는 Java 백엔드 제품화 전 테스트용 기준이다. Java 구현 시에도 요청/응답 구조는 동일하게 유지하는 것을 권장한다.

## 2. Endpoint

```http
POST /ai/care-summary
Content-Type: application/json
```

테스트용:

```http
GET /ai/demo-care-summary
GET /health
```

## 3. Request Body

```json
{
  "productId": "MCM001",
  "productName": "Aren Crossbody",
  "deviceId": "SC001",
  "materialId": "coated_cowhide",
  "materialSubtypes": ["grained_coated_cowhide"],
  "color": "Cognac",
  "analysisWindowDays": 7,
  "samplingWindowSeconds": 600,
  "sensorReadings": [
    {
      "sequence": 1,
      "measuredAt": 1735123456,
      "temperature": 24.8,
      "humidity": 68.4,
      "maxShock": 0.32,
      "motionCount": 2
    }
  ],
  "userEvents": {
    "wetEventReported": false,
    "directHeatEventReported": false,
    "directSunExposureReported": false,
    "abrasiveContactEvent": false,
    "overloadReported": false
  },
  "userSymptoms": {
    "visibleMouldReported": false,
    "mustyOdourReported": false,
    "waterStainReported": false,
    "stickyOrTackyCoatingReported": false,
    "crackingReported": false,
    "stiffnessReported": false,
    "napMattingReported": false,
    "cornerWearReported": false,
    "shapeCollapseReported": false
  },
  "usageLog": {
    "usageDays7d": 0,
    "usageDays30d": 0,
    "restDays30d": 0
  },
  "llm": {
    "enabled": false,
    "model": "gpt-5-mini",
    "locale": "ko-KR",
    "screenContexts": [
      "home_summary",
      "diagnosis_home",
      "care_report",
      "environment_detail",
      "care_guide",
      "reservation_cta"
    ]
  }
}
```

## 4. Response Body

```json
{
  "schemaVersion": "mxis-ai-api-v0.1",
  "product": {},
  "featureSummary": {},
  "aiCareSummary": {
    "generatedAt": "2026-08-17T00:00:00Z",
    "analysisWindowDays": 7,
    "dataSufficiency": {},
    "productCondition": {},
    "stressLabels": {},
    "careDecision": {},
    "explanation": {},
    "llmCopy": {},
    "copyGeneration": {
      "source": "openai|deterministic_fallback",
      "model": "gpt-5-mini|null",
      "error": null,
      "rawResponseId": "resp_..."
    },
    "reservationCta": {},
    "evidence": {},
    "debug": {}
  }
}
```

프론트 MVP에서는 우선 다음 필드를 사용하면 된다.

- `aiCareSummary.productCondition.label`
- `aiCareSummary.productCondition.score`
- `aiCareSummary.productCondition.summary`
- `aiCareSummary.stressLabels`
- `aiCareSummary.careDecision.recommendedActions`
- `aiCareSummary.careDecision.doNotDo`
- `aiCareSummary.explanation.short`
- `aiCareSummary.explanation.reasonBullets`
- `aiCareSummary.llmCopy.homeSummary`
- `aiCareSummary.llmCopy.diagnosisHome`
- `aiCareSummary.llmCopy.careReport`
- `aiCareSummary.llmCopy.environmentDetail`
- `aiCareSummary.llmCopy.careGuide`
- `aiCareSummary.reservationCta`
- `aiCareSummary.copyGeneration.source`

## 5. 실행 방법

```bash
python3 prototype/mxis_ai_api_server.py --host 127.0.0.1 --port 8765
```

테스트:

```bash
curl http://127.0.0.1:8765/health
curl http://127.0.0.1:8765/ai/demo-care-summary
curl -X POST http://127.0.0.1:8765/ai/care-summary \
  -H "Content-Type: application/json" \
  --data @examples/care-summary.request.json
```

OpenAI 설명 생성을 켜려면 다음 환경 변수를 사용한다.

```bash
OPENAI_API_KEY=sk-... \
MXIS_USE_OPENAI=true \
OPENAI_MODEL=gpt-5-mini \
python3 prototype/mxis_ai_api_server.py --host 127.0.0.1 --port 8765
```

또는 요청 body에서 `llm.enabled = true`로 켤 수 있다. OpenAI 호출 실패, schema 검증 실패, 금지 표현 검출, API key 누락 시에는 deterministic fallback copy를 반환한다.

## 6. MVP 제약

- LLM은 판단을 새로 만들지 않고 사용자-facing copy만 생성한다.
- `explanation`과 `llmCopy`는 Prompt Spec 정책을 반영한다.
- UV/light는 센서 입력이 없으면 `UNKNOWN`이다.
- IMU는 손상 판단이 아니라 움직임/사용 노출 proxy로만 사용한다.
- 데이터가 24시간 기준을 채우지 못하면 관리 결론보다 데이터 수집 상태를 우선 표시한다.
