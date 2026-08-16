# MXIS LLM Explanation Prompt Spec v0.1

작성일: 2026-08-17

상태: MVP Draft

연결 문서:

- `docs/04-ai-output-contract.md`
- `docs/02-feature-extractor.md`
- `docs/03-rule-evaluator.md`
- `docs/05-weak-supervision.md`

## 1. 목적

LLM Explanation은 Feature Extractor와 Rule Evaluator가 만든 구조화 결과를 사용자가 이해할 수 있는 짧은 설명으로 바꾸는 계층이다.

```text
SensorReading
-> Feature Extractor
-> Rule Evaluator
-> AI Output Composer
-> LLM Explanation
-> Frontend
```

LLM의 역할은 판단을 새로 만드는 것이 아니다. 이미 계산된 `stressLabels`, `careNeed`, `inspectionNeed`, `recommendedActions`, `triggeredRules`, `featureSummary`를 바탕으로 안전하고 일관된 사용자 문구를 생성한다.

## 2. 핵심 원칙

LLM은 다음을 지켜야 한다.

- 손상 확률을 말하지 않는다.
- 센서값만으로 "손상됨", "곰팡이가 생김", "가죽이 갈라짐"이라고 단정하지 않는다.
- `HIGH`는 강한 노출 상태이지 손상 확정이 아니다.
- `INSPECTION_REQUIRED`는 visible symptom, hard trigger, 사용자 보고 증상 중심으로 설명한다.
- UV/light는 MVP 센서로 직접 측정하지 않으므로, 직접 입력이 없으면 `UNKNOWN`으로 설명한다.
- IMU의 `maxShock`, `motionCount`는 handling exposure proxy이지 제품 손상 threshold가 아니다.
- 순간 온습도보다 안정 범위를 벗어난 누적 시간이 중요하다고 설명한다.
- 근거 없는 threshold, 수리 가능성, 비용, 브랜드 보증 여부를 말하지 않는다.

## 3. LLM 입력 스키마

LLM에는 raw sensor 전체를 넣지 않는다. 필요한 요약만 넣는다.

```json
{
  "locale": "ko-KR",
  "screenContext": "home_summary",
  "product": {
    "productId": "MCM001",
    "name": "Aren Crossbody",
    "materialId": "coated_cowhide",
    "materialSubtypes": ["grained_coated_cowhide"],
    "color": "Cognac"
  },
  "analysis": {
    "analysisWindowDays": 7,
    "dataSufficiency": {
      "status": "SUFFICIENT",
      "reason": null,
      "validReadingCount": 144,
      "coverageHours": 24.0,
      "lastMeasuredAt": "2026-08-16T09:40:00Z"
    },
    "featureSummary": {
      "avgTemperature": 24.8,
      "avgHumidity": 56.4,
      "rhHoursGt65": 10.0,
      "rhHoursGt80": 0.0,
      "rhHoursGt90": 0.0,
      "leatherMouldDose": 0.0042,
      "tempHoursAbove30": 0.0,
      "warmMoistExposureHours": 0.0,
      "rhHoursLt30": 0.0,
      "motionTotal": 72,
      "activeWindowCount": 36,
      "maxShock": 0.34
    },
    "stressLabels": {
      "humidity": "CAUTION",
      "temperatureHeat": "LOW",
      "dryness": "LOW",
      "handling": "LOW",
      "usageRest": "LOW",
      "uvLight": "UNKNOWN"
    },
    "careDecision": {
      "careNeed": "LOW_MEDIUM",
      "inspectionNeed": "NONE",
      "recommendedActions": [
        "ventilate_storage_area",
        "store_in_dust_bag"
      ],
      "doNotDo": [
        "avoid_direct_heat"
      ]
    },
    "evidence": {
      "triggeredRules": [
        "leather_sustained_rh_gt_65",
        "light_not_measured_by_available_sensors"
      ],
      "matchedKbEntries": ["KB-001"],
      "sourceLevel": "A"
    }
  }
}
```

## 4. LLM 출력 스키마

LLM은 반드시 JSON만 반환한다. Markdown, 설명문, 추가 키를 반환하지 않는다.

```json
{
  "short": "최근 고습 노출이 일부 누적되어 보관 환경 조정이 권장됩니다.",
  "reasonBullets": [
    "최근 분석 기간 동안 습도가 안정 범위를 벗어난 시간이 확인되었습니다.",
    "현재 점검이 필요한 표면 증상은 보고되지 않았습니다."
  ],
  "sensorLimitations": [
    "MVP 센서는 UV/light를 직접 측정하지 않습니다.",
    "표면 얼룩, 갈라짐, 끈적임은 사용자 확인이 필요합니다."
  ],
  "careCopy": {
    "primaryActionTitle": "보관 공간 환기",
    "primaryActionDescription": "가방을 더스트백에 넣되, 보관 공간은 가볍게 환기해 습기가 머무르지 않게 해주세요.",
    "doNotDo": [
      "드라이어, 라디에이터, 차량 내부 열로 말리지 마세요."
    ]
  },
  "reservationCopy": {
    "title": null,
    "description": null,
    "prefillNote": null
  }
}
```

## 5. Screen Context별 길이

| screenContext | 목적 | short | reasonBullets | sensorLimitations |
| --- | --- | --- | --- | --- |
| `home_summary` | 홈 한 줄 상태 | 40자 이내 권장 | 0-2개 | 0-1개 |
| `diagnosis_home` | 케어 진단 홈 | 60자 이내 권장 | 2개 | 1-2개 |
| `care_report` | 기간 리포트 | 80자 이내 권장 | 2-4개 | 1-2개 |
| `environment_detail` | 그래프 해석 | 80자 이내 권장 | 2-4개 | 1-2개 |
| `care_guide` | 개인화 관리 가이드 | 80자 이내 권장 | 2-3개 | 1개 |
| `reservation_cta` | 예약 CTA | CTA 중심 | 0-2개 | 필요 시 1개 |

## 6. System Prompt

```text
You are MXIS Care Explanation Writer.

Your job is to convert structured material-care analysis into concise Korean user-facing copy.

You must not create new risk judgments, probabilities, thresholds, diagnoses, repair estimates, or inspection requirements.
Use only the provided structured input.

The product is a luxury bag. Write calmly, precisely, and preventively.
Do not overstate damage. Sensor-only exposure means exposure, not confirmed damage.

Return valid JSON only.
```

## 7. Developer Prompt

```text
Follow these rules:

1. Output language must be Korean unless input.locale says otherwise.
2. Use polite but concise Korean.
3. Do not mention "AI가 판단했습니다" unless the product UI explicitly needs it.
4. Never output damage probability, mould probability, cracking probability, repair cost, warranty advice, or brand-authenticity advice.
5. If dataSufficiency.status is not SUFFICIENT, focus on data collection status and avoid care conclusions.
6. If uvLight is UNKNOWN because light is not measured, say that UV/light is not directly measured by the current sensor.
7. If handling is based on IMU, explain it as "움직임/사용 노출" rather than "충격 손상".
8. If inspectionNeed is REQUIRED, recommend brand or specialist inspection without guaranteeing damage.
9. If inspectionNeed is CONDITIONAL, ask the user to check visible symptoms and offer inspection as an option.
10. Keep the output within the schema. Do not add extra fields.
```

## 8. User Prompt Template

```text
Create MXIS explanation JSON for the following structured analysis.

Input:
{{analysis_json}}

Required output schema:
{
  "short": "string",
  "reasonBullets": ["string"],
  "sensorLimitations": ["string"],
  "careCopy": {
    "primaryActionTitle": "string|null",
    "primaryActionDescription": "string|null",
    "doNotDo": ["string"]
  },
  "reservationCopy": {
    "title": "string|null",
    "description": "string|null",
    "prefillNote": "string|null"
  }
}
```

## 9. 라벨별 문구 규칙

### 9.1 Data Sufficiency

| status | 문구 방향 | 금지 |
| --- | --- | --- |
| `SUFFICIENT` | 분석 결과 설명 가능 | 없음 |
| `INSUFFICIENT_DATA` | "분석을 위해 데이터를 수집 중" | 관리 필요 단정 |
| `STALE_DATA` | "최근 동기화가 필요" | 현재 상태 단정 |
| `NO_DATA` | "아직 유효 데이터 없음" | 상태 평가 |

### 9.2 Stress Label

| label | 사용자 표현 | 설명 기준 |
| --- | --- | --- |
| `LOW` | 안정적 | 특별한 노출이 확인되지 않음 |
| `CAUTION` | 주의 | 안정 범위 이탈 또는 예방 관리 필요 |
| `ELEVATED` | 관리 필요 | 반복/복합 노출, 민감 소재 이벤트 |
| `HIGH` | 강한 관리 필요 | 강한 노출 band 도달, 손상 확정 아님 |
| `INSPECTION_REQUIRED` | 점검 권장 | 증상/hard trigger 기반 |
| `UNKNOWN` | 판단 보류 | 센서/입력 부족 |

## 10. Risk Factor별 Explanation Policy

### 10.1 Humidity

허용:

- "습도가 안정 범위를 벗어난 시간이 누적되었습니다."
- "고습 노출이 반복되어 환기와 보관 환경 조정이 권장됩니다."
- "곰팡이 발생을 단정할 수는 없지만, 고습 환경은 예방 관리가 필요한 조건입니다."

금지:

- "곰팡이가 생겼습니다."
- "곰팡이 위험 30%입니다."
- "가죽이 손상되었습니다."

### 10.2 Temperature/Heat

허용:

- "높은 온도와 습도가 함께 나타난 시간이 있어 직접 열을 피하는 것이 좋습니다."
- "직접 열원 사용은 피해주세요."

금지:

- "열로 코팅이 변형되었습니다." 단, 사용자가 끈적임/부풀음 증상을 보고한 경우에는 "점검 권장" 가능.

### 10.3 Dryness

허용:

- "낮은 습도 노출이 지속되어 가죽이 건조해지지 않도록 보관 환경을 조정하는 것이 좋습니다."
- "제습제를 무분별하게 가까이 두는 것은 피해주세요."

금지:

- "가죽이 갈라졌습니다." 단, 사용자가 갈라짐을 보고한 경우에는 "갈라짐 증상이 보고되어 점검 권장" 가능.

### 10.4 UV/Light

허용:

- "현재 센서는 UV/light를 직접 측정하지 않습니다."
- "직사광선 노출이 보고된 경우, 변색 예방을 위해 보관 위치를 조정해주세요."

금지:

- 사용자 입력 없이 "햇빛에 오래 노출되었습니다."

### 10.5 Physical Shock/Abrasion

허용:

- "`motionCount`와 `maxShock`는 움직임/사용 노출을 보는 참고 지표입니다."
- "움직임이 많은 기간이 있어 모서리 마찰과 과적재를 피하는 관리가 권장됩니다."

금지:

- "충격으로 손상되었습니다."
- "2g 이상이면 가방이 손상됩니다."

### 10.6 Continuous Usage/Rest

허용:

- "최근 사용 빈도가 높아 사용 후 닦기와 형태 유지 보관을 권장합니다."
- "동일 제품을 연속 사용했다면 보관 중 형태를 받쳐주세요."

금지:

- "며칠 이상 사용하면 손상됩니다."

## 11. Care Action Copy Map

| action code | title | description |
| --- | --- | --- |
| `ventilate_storage_area` | 보관 공간 환기 | 가방을 보관하는 공간에 습기가 머무르지 않도록 가볍게 환기해주세요. |
| `store_in_dust_bag` | 더스트백 보관 | 먼지와 빛 노출을 줄이기 위해 통풍 가능한 상태로 더스트백에 보관해주세요. |
| `support_shape_in_storage` | 형태 유지 보관 | 보관 중에는 내부를 가볍게 받쳐 형태가 무너지지 않게 해주세요. |
| `blot_with_lint_free_cloth` | 부드러운 천으로 물기 제거 | 젖은 부분은 문지르지 말고 부드러운 천으로 눌러 물기를 제거해주세요. |
| `dry_at_room_temperature` | 실온에서 자연 건조 | 직접 열을 쓰지 말고 통풍되는 실온에서 천천히 말려주세요. |
| `avoid_direct_heat` | 직접 열 피하기 | 드라이어, 라디에이터, 차량 내부 열로 말리지 마세요. |
| `avoid_direct_sunlight` | 직사광선 피하기 | 창가나 직사광선이 닿는 위치에 오래 두지 마세요. |
| `avoid_desiccant_for_leather` | 무분별한 제습제 피하기 | 가죽 가까이에 강한 제습제를 오래 두는 것은 피해주세요. |
| `avoid_abrasive_surfaces` | 거친 표면 피하기 | 바닥, 벽면, 거친 테이블과의 반복 마찰을 피해주세요. |
| `avoid_overpacking` | 과적재 피하기 | 무거운 내용물을 오래 넣어두지 말고 핸들/형태 부담을 줄여주세요. |
| `rotate_usage` | 사용 주기 분산 | 사용 빈도가 높다면 다른 제품과 번갈아 사용해 휴식 시간을 주세요. |
| `brush_suede_gently_when_dry` | 스웨이드 가볍게 브러싱 | 완전히 마른 상태에서 전용 브러시로 결을 가볍게 정리해주세요. |
| `avoid_oils_perfumes_sanitizers` | 오일/향수 접촉 피하기 | 오일, 향수, 화장품, 손소독제가 닿지 않게 주의해주세요. |
| `escalate_to_brand_or_specialist` | 전문가 점검 | 표면 증상이 확인된 경우 브랜드 또는 전문 케어 서비스를 통해 점검을 받아보세요. |

## 12. Reservation Copy Rules

| inspectionNeed | reservationCopy |
| --- | --- |
| `NONE` | all `null` |
| `CONDITIONAL` | 증상 확인 후 상담/점검 옵션 제공 |
| `REQUIRED` | 브랜드/전문가 점검 권장 |

예시:

```json
{
  "title": "상태 점검을 권장합니다",
  "description": "표면 증상이 보고되어 브랜드 또는 전문 케어 서비스를 통한 확인이 좋습니다.",
  "prefillNote": "최근 습기 노출 이후 표면 상태 점검을 요청합니다."
}
```

## 13. Few-shot Examples

### 13.1 안정 상태

입력 요약:

```json
{
  "dataSufficiency": {"status": "SUFFICIENT"},
  "stressLabels": {
    "humidity": "LOW",
    "temperatureHeat": "LOW",
    "dryness": "LOW",
    "handling": "LOW",
    "usageRest": "LOW",
    "uvLight": "UNKNOWN"
  },
  "careDecision": {
    "careNeed": "LOW",
    "inspectionNeed": "NONE",
    "recommendedActions": []
  }
}
```

출력:

```json
{
  "short": "현재 제공된 데이터 기준으로 보관 상태는 안정적입니다.",
  "reasonBullets": [
    "최근 온습도와 움직임 노출에서 특별한 관리 신호가 확인되지 않았습니다."
  ],
  "sensorLimitations": [
    "현재 센서는 UV/light를 직접 측정하지 않습니다."
  ],
  "careCopy": {
    "primaryActionTitle": null,
    "primaryActionDescription": null,
    "doNotDo": []
  },
  "reservationCopy": {
    "title": null,
    "description": null,
    "prefillNote": null
  }
}
```

### 13.2 고습 CAUTION

출력:

```json
{
  "short": "최근 고습 노출이 일부 누적되어 보관 환경 조정이 권장됩니다.",
  "reasonBullets": [
    "분석 기간 중 습도가 안정 범위를 벗어난 시간이 확인되었습니다.",
    "현재 점검이 필요한 표면 증상은 보고되지 않았습니다."
  ],
  "sensorLimitations": [
    "센서값은 노출 상태를 보여주며, 실제 표면 증상은 별도 확인이 필요합니다."
  ],
  "careCopy": {
    "primaryActionTitle": "보관 공간 환기",
    "primaryActionDescription": "가방을 더스트백에 넣되, 보관 공간은 가볍게 환기해 습기가 머무르지 않게 해주세요.",
    "doNotDo": [
      "젖은 느낌이 있을 때 드라이어 같은 직접 열로 말리지 마세요."
    ]
  },
  "reservationCopy": {
    "title": null,
    "description": null,
    "prefillNote": null
  }
}
```

### 13.3 점검 필요

출력:

```json
{
  "short": "표면 증상이 보고되어 전문가 점검을 권장합니다.",
  "reasonBullets": [
    "사용자 입력에서 점검이 필요한 증상이 확인되었습니다.",
    "센서 데이터만으로 손상을 확정하지는 않지만, 증상이 있는 경우 직접 확인이 우선입니다."
  ],
  "sensorLimitations": [
    "현재 센서는 표면 얼룩, 갈라짐, 끈적임을 직접 감지하지 않습니다."
  ],
  "careCopy": {
    "primaryActionTitle": "전문가 점검",
    "primaryActionDescription": "제품을 더 문지르거나 열을 가하지 말고 브랜드 또는 전문 케어 서비스를 통해 상태를 확인해주세요.",
    "doNotDo": [
      "표면 증상을 지우기 위해 강하게 문지르지 마세요.",
      "직접 열이나 임의 세척제를 사용하지 마세요."
    ]
  },
  "reservationCopy": {
    "title": "전문가 점검을 권장합니다",
    "description": "표면 증상이 보고되어 브랜드 또는 전문 케어 서비스를 통한 확인이 좋습니다.",
    "prefillNote": "MXIS 케어 분석에서 점검 권장 신호가 확인되었습니다."
  }
}
```

## 14. Validation Rules

LLM 출력은 저장 전 다음 검사를 통과해야 한다.

```text
valid_json == true
required_keys_present == true
no_extra_keys == true
no_forbidden_claims == true
length_policy_passed == true
inspection_copy_matches_inspectionNeed == true
uv_unknown_limitation_present_when_uvLight_UNKNOWN == true
data_insufficient_avoids_care_conclusion == true
```

금지어/주의어 후보:

```text
손상되었습니다
곰팡이가 생겼습니다
갈라졌습니다
확률
수리비
보증
정품
가품
2g 이상이면 손상
```

주의: 사용자가 증상을 직접 보고한 경우에는 "보고되었습니다", "확인해보는 것이 좋습니다"로 표현한다.

## 15. Integration Plan

MVP 구현 순서:

1. Backend가 Feature Extractor와 Rule Evaluator 결과를 만든다.
2. AI Output Composer가 LLM input JSON을 만든다.
3. LLM이 explanation JSON만 생성한다.
4. Backend가 JSON schema와 금지 표현을 검증한다.
5. 실패 시 deterministic fallback copy를 사용한다.
6. 프론트는 `aiCareSummary.explanation`과 `reservationCta`를 표시한다.

Fallback 원칙:

- LLM 실패 시에도 care decision은 유지한다.
- 설명 문구만 deterministic template으로 대체한다.
- inspectionNeed가 `REQUIRED`인 경우 fallback에서도 점검 CTA는 유지한다.
