# MXIS AI Java Backend Integration Guide

이 문서는 현재 Python prototype을 Java/Spring 백엔드로 옮기기 위한 작업 기준입니다.

## 1. 권장 패키지 구조

```text
com.mxis.ai
├── controller
│   └── AiCareSummaryController
├── service
│   ├── FeatureExtractorService
│   ├── RuleEvaluatorService
│   └── AiCareSummaryComposer
├── dto
│   ├── AiCareSummaryRequest
│   ├── SensorReadingDto
│   └── AiCareSummaryResponse
├── model
│   ├── ExposureFeatures
│   ├── StressLabel
│   ├── CareNeed
│   └── InspectionNeed
└── knowledge
    └── MaterialKnowledgeRepository
```

## 2. 구현 순서

1. DTO부터 고정한다.
2. `FeatureExtractorService`를 구현한다.
3. `RuleEvaluatorService`를 구현한다.
4. `AiCareSummaryComposer`를 구현한다.
5. 선택적으로 `OpenAiExplanationService`를 구현한다.
6. Controller에서 `POST /ai/care-summary`를 연동한다.
7. Python validation case를 Java unit test로 옮긴다.

## 3. Controller Shape

```java
@RestController
@RequestMapping("/ai")
public class AiCareSummaryController {
    private final FeatureExtractorService featureExtractor;
    private final RuleEvaluatorService ruleEvaluator;
    private final AiCareSummaryComposer composer;

    @PostMapping("/care-summary")
    public AiCareSummaryResponse careSummary(@RequestBody AiCareSummaryRequest request) {
        ExposureFeatures features = featureExtractor.extract(request);
        RuleEvaluationResult result = ruleEvaluator.evaluate(request, features);
        return composer.compose(request, features, result);
    }
}
```

## 4. SensorReading Mapping

Smart Charm 입력은 다음 필드를 그대로 받는다.

```java
public record SensorReadingDto(
    Integer sequence,
    Long measuredAt,
    Double temperature,
    Double humidity,
    Double maxShock,
    Integer motionCount
) {}
```

주의:

- `measuredAt = 0`은 invalid timestamp로 처리한다.
- `temperature` 또는 `humidity`가 없으면 해당 reading은 환경 feature 계산에서 제외한다.
- `maxShock`와 `motionCount`가 없으면 IMU feature quality flag에 반영한다.
- `maxShock`는 손상 threshold가 아니라 handling exposure proxy다.

## 5. Feature Extractor Porting Notes

Python 기준 함수:

```text
prototype/mxis_feature_extractor.py
```

Java service에서 구현해야 하는 주요 feature:

- `dataSufficiency.status`
- `coverageHours`
- `rhHoursGt65`
- `rhHoursGt70`
- `rhHoursGt80`
- `rhHoursGt90`
- `rhHoursLt30`
- `leatherMouldDose`
- `tempHoursAbove30`
- `warmMoistExposureHours`
- `motionTotal`
- `activeWindowCount`
- `maxShock`

최소 기준:

```text
minValidReadings = 24
minCoverageHours = 24
defaultSamplingWindowSeconds = 600
```

## 6. Rule Evaluator Porting Notes

Python 기준 함수:

```text
prototype/mxis_rule_evaluator.py
```

Java에서는 deterministic rule로 구현한다.

중요 정책:

- `LOW`, `CAUTION`, `ELEVATED`, `HIGH`, `INSPECTION_REQUIRED`, `UNKNOWN` 순서 유지
- `HIGH`는 손상 확정이 아니라 강한 노출 상태
- `INSPECTION_REQUIRED`는 사용자 증상 또는 hard trigger 중심
- UV/light는 MVP 센서로 직접 측정하지 않으므로 기본 `UNKNOWN`
- IMU 기반 handling signal은 sensor-only 상황에서 최대 `CAUTION`

## 7. Response Composer

프론트 응답은 다음 블록을 유지한다.

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

MVP에서 `explanation`은 LLM 호출 없이 deterministic fallback copy로도 동작해야 한다. LLM을 붙일 경우 `docs/06-llm-explanation.md`의 정책을 따른다.

OpenAI를 붙일 경우에도 판단은 바꾸지 않는다. OpenAI는 다음 값만 생성한다.

- `explanation`
- `llmCopy.homeSummary`
- `llmCopy.diagnosisHome`
- `llmCopy.careReport`
- `llmCopy.environmentDetail`
- `llmCopy.careGuide`
- `llmCopy.reservationCta`

권장 backend flow:

```text
FeatureExtractorService
-> RuleEvaluatorService
-> AiCareSummaryComposer deterministic base response
-> OpenAiExplanationService optional copy generation
-> schema/forbidden-claim validation
-> fallback copy on failure
```

필수 환경 변수:

```text
OPENAI_API_KEY
OPENAI_MODEL=gpt-5-mini
MXIS_USE_OPENAI=true
```

## 8. Java Test Migration

다음 파일을 Java unit test fixture로 옮긴다.

- `tests/fixtures/feature-extractor-cases.json`
- `tests/fixtures/rule-evaluator-cases.json`
- `tests/fixtures/synthetic-dataset.sample.json`

권장 테스트:

- 데이터 부족이면 `Collecting Data`
- 24시간 sufficient case면 정상 label 생성
- RH >65% 지속이면 humidity `CAUTION`
- leather mould dose 도달이면 humidity `HIGH`
- visible mould reported면 inspection `REQUIRED`
- `motionCount` 누적은 handling `CAUTION`까지만 허용

## 9. Backend TODO

- Product DB에서 `materialId`, `materialSubtypes`를 안정적으로 공급
- SensorReading table query에서 analysis window 기준 정렬/필터링
- 7일/30일 aggregation cache 고려
- LLM Explanation 사용 여부 결정
- 프론트와 `aiCareSummary` 필드 노출 범위 확정
