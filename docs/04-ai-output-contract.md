# MXIS AI Output Contract v0.1

작성일: 2026-08-16

상태: MVP Draft

목적: Feature Extractor와 Care-model-v1 Rule Evaluator 결과를 프론트엔드 화면에 전달하기 위한 API 응답 계약을 정의한다.

## 1. 설계 원칙

MVP에서는 프론트 화면 렌더링에 필요한 최소 정보를 우선 제공한다.

동시에 추후 확장을 위해 다음 영역을 분리한다.

```text
dataSufficiency
productCondition
stressLabels
careDecision
explanation
reservationCta
debug / evidence
```

핵심 원칙:

- AI는 손상 확률을 제공하지 않는다.
- 센서값만으로 "손상됨"을 말하지 않는다.
- `HIGH`도 손상 확정이 아니라 강한 노출 상태다.
- `INSPECTION_REQUIRED`는 visible symptom 또는 hard trigger 중심이다.
- UV/light는 MVP 센서로 측정하지 않으므로 기본 `UNKNOWN`이다.
- IMU는 damage threshold가 아니라 handling exposure proxy다.

## 2. MVP 화면 범위

첨부된 프론트/백엔드 전달 데이터 문서 기준, AI output이 필요한 화면은 다음이다.

| 화면 | 목적 | AI output 필요도 |
| --- | --- | --- |
| 메인 홈 | 제품 상태와 한 줄 안내 | 필수 |
| 케어 진단 홈 | 현재 센서 상태와 컨디션 설명 | 필수 |
| 상태 리포트 | 기간별 해석과 관리 추천 | 필수 |
| 환경 데이터 상세 | 그래프 해석과 threshold band | 필수 |
| 관리 가이드 | 소재별/상황별 관리 팁 | 필수 |
| 예약 CTA | 점검/예약 권장 여부 | MVP 선택, 확장 대비 포함 |

## 3. 공통 응답 블록: `aiCareSummary`

모든 주요 화면은 공통으로 `aiCareSummary`를 받을 수 있다.

```json
{
  "aiCareSummary": {
    "generatedAt": "2026-08-16T09:41:00Z",
    "analysisWindowDays": 7,
    "dataSufficiency": {
      "status": "SUFFICIENT",
      "reason": null,
      "validReadingCount": 144,
      "coverageHours": 24.0,
      "lastMeasuredAt": "2026-08-16T09:40:00Z",
      "lastSyncedAt": "2026-08-16T09:41:00Z"
    },
    "productCondition": {
      "label": "Standard",
      "score": 76,
      "primaryFactor": "humidity",
      "summary": "최근 습도가 안정 범위를 벗어난 시간이 있어 보관 환경 조정이 권장됩니다."
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
        {
          "code": "ventilate_storage_area",
          "title": "보관 공간 환기",
          "description": "가방을 보관하는 공간을 가볍게 환기해주세요.",
          "priority": 1
        }
      ],
      "doNotDo": [
        {
          "code": "avoid_direct_heat",
          "title": "직접 열 사용 피하기",
          "description": "드라이어, 라디에이터, 차량 내부 열로 말리지 마세요."
        }
      ]
    },
    "explanation": {
      "short": "최근 고습 노출이 일부 누적되어 예방 관리가 권장됩니다.",
      "reasonBullets": [
        "제공된 센서 데이터 기준으로 습도가 안정 범위를 벗어난 시간이 확인되었습니다.",
        "현재 점검이 필요한 증상은 보고되지 않았습니다."
      ],
      "sensorLimitations": [
        "MVP 센서는 UV/light를 직접 측정하지 않습니다.",
        "표면 증상은 사용자 입력 또는 향후 이미지 분석이 필요합니다."
      ]
    },
    "reservationCta": {
      "recommended": false,
      "level": "NONE",
      "title": null,
      "description": null,
      "prefillNote": null
    }
  }
}
```

## 4. Enum 정의

### 4.1 `dataSufficiency.status`

| value | 의미 | 프론트 처리 |
| --- | --- | --- |
| `SUFFICIENT` | AI 분석 가능 | 정상 카드 표시 |
| `INSUFFICIENT_DATA` | 최소 데이터 부족 | 수집중 화면 |
| `STALE_DATA` | 마지막 sync/measurement가 오래됨 | 재연결/동기화 안내 |
| `NO_DATA` | 유효 데이터 없음 | 미수집 화면 |

### 4.2 `dataSufficiency.reason`

| value | 의미 |
| --- | --- |
| `NO_VALID_READING` | 유효 SensorReading 없음 |
| `MIN_READING_COUNT_NOT_MET` | 최소 reading 수 미달 |
| `MIN_COVERAGE_HOURS_NOT_MET` | 최소 24시간 coverage 미달 |
| `MISSING_TEMPERATURE` | 온도 없음 |
| `MISSING_HUMIDITY` | 습도 없음 |
| `STALE_LAST_SYNC` | 마지막 동기화 오래됨 |

### 4.3 `productCondition.label`

프론트 표시용 제품 상태.

| value | 내부 기준 | 의미 |
| --- | --- | --- |
| `Excellent` | 주요 tier가 `LOW` 중심 | 현재 데이터 기준 안정적 |
| `Standard` | `CAUTION` 또는 일부 `ELEVATED` | 일상 관리 권장 |
| `Needs Attention` | `HIGH` 또는 `INSPECTION_REQUIRED` | 강한 관리/점검 확인 필요 |
| `Collecting Data` | 데이터 부족 | 분석 전 |

주의:

- `Excellent`는 제품 무결성 보장이 아니다.
- `Needs Attention`은 손상 확정이 아니다.

### 4.4 `stressLabels.*`

| value | 의미 |
| --- | --- |
| `LOW` | 의미 있는 노출 없음 |
| `CAUTION` | 안정 범위 이탈, 예방 조정 필요 |
| `ELEVATED` | 반복 노출 또는 민감 소재와 이벤트 결합 |
| `HIGH` | damage-supporting exposure band 도달, 손상 확정 아님 |
| `INSPECTION_REQUIRED` | 증상/hard trigger 기반 점검 필요 |
| `UNKNOWN` | 센서/입력 부족 |

### 4.5 `careDecision.careNeed`

| value | 의미 |
| --- | --- |
| `LOW` | 특별한 관리 액션 없음 |
| `LOW_MEDIUM` | 가벼운 예방 관리 권장 |
| `MEDIUM` | 관리 필요 |
| `MEDIUM_HIGH` | 빠른 관리와 증상 확인 권장 |
| `HIGH` | 강한 관리 또는 점검 필요 |

### 4.6 `careDecision.inspectionNeed`

| value | 의미 | 프론트 처리 |
| --- | --- | --- |
| `NONE` | 점검 필요 없음 | 예약 CTA 숨김 또는 낮은 우선순위 |
| `CONDITIONAL` | 증상 확인 후 점검 고려 | 증상 질문/예약 옵션 |
| `REQUIRED` | 점검 권장 | 예약 CTA 강조 |

### 4.7 `reservationCta.level`

| value | 의미 |
| --- | --- |
| `NONE` | 예약 권장 없음 |
| `OPTIONAL` | 사용자가 원하면 예약 가능 |
| `RECOMMENDED` | 점검/상담 권장 |
| `REQUIRED` | 전문가/브랜드 점검 강하게 권장 |

## 5. Product Condition Score

`score`는 손상 확률이 아니다. 프론트 원형 그래프를 위한 care condition score다.

MVP 기본 매핑:

| condition | score range |
| --- | --- |
| `Excellent` | 85-100 |
| `Standard` | 60-84 |
| `Needs Attention` | 0-59 |
| `Collecting Data` | null |

초기 deterministic score:

```text
base = 100

CAUTION count      * -8
ELEVATED count     * -18
HIGH count         * -35
INSPECTION_REQUIRED * -50
STALE_DATA         * -10
INSUFFICIENT_DATA  -> score = null
```

하한/상한:

```text
score = clamp(score, 0, 100)
```

주의:

- 점수는 사용자-facing UI용 상태 점수다.
- 제품 가치, 손상률, 수리 필요 확률로 해석하면 안 된다.

## 6. Care Action Object

```json
{
  "code": "dry_at_room_temperature",
  "title": "실온에서 자연 건조",
  "description": "젖은 경우 직접 열을 쓰지 말고 통풍되는 실온에서 말려주세요.",
  "priority": 1,
  "category": "humidity",
  "durationHint": "오늘",
  "isPrimary": true
}
```

MVP action code:

| code | title |
| --- | --- |
| `ventilate_storage_area` | 보관 공간 환기 |
| `store_in_dust_bag` | 더스트백 보관 |
| `support_shape_in_storage` | 형태 유지 보관 |
| `blot_with_lint_free_cloth` | 부드러운 천으로 물기 제거 |
| `dry_at_room_temperature` | 실온에서 자연 건조 |
| `avoid_direct_heat` | 직접 열 피하기 |
| `avoid_direct_sunlight` | 직사광선 피하기 |
| `avoid_desiccant_for_leather` | 가죽에 무분별한 제습제 사용 피하기 |
| `avoid_abrasive_surfaces` | 거친 표면 피하기 |
| `avoid_overpacking` | 과적재 피하기 |
| `rotate_usage` | 사용 주기 분산 |
| `brush_suede_gently_when_dry` | 마른 상태에서 스웨이드 가볍게 브러싱 |
| `avoid_oils_perfumes_sanitizers` | 오일/향수/손소독제 접촉 피하기 |
| `escalate_to_brand_or_specialist` | 브랜드/전문가 점검 |

## 7. 화면별 Contract

## 7.1 메인 홈: `GET /home/summary`

MVP에서 홈은 `aiCareSummary` 일부만 필요하다.

```json
{
  "user": {
    "displayName": "김멋사"
  },
  "product": {
    "productId": "MCM001",
    "name": "Aren Crossbody",
    "material": "coated_cowhide",
    "color": "Cognac",
    "imageUrl": "https://..."
  },
  "device": {
    "deviceId": "SC001",
    "connectionStatus": "CONNECTED",
    "lastSyncedAt": "2026-08-16T09:41:00Z"
  },
  "aiCareSummary": {
    "dataSufficiency": {},
    "productCondition": {},
    "stressLabels": {},
    "careDecision": {},
    "explanation": {
      "short": "최근 습도가 안정 범위를 벗어난 시간이 있어 보관 환경 조정이 권장됩니다."
    }
  },
  "reservation": {
    "hasUpcoming": false,
    "summary": null
  }
}
```

프론트 사용:

- `productCondition.label`: 상태 뱃지
- `productCondition.score`: 원형 그래프
- `explanation.short`: 홈 안내 문구
- `dataSufficiency.status`: 데이터 수집중/미수집 분기
- `device.connectionStatus`: Charm 연결 끊김 배너

## 7.2 케어 진단 홈: `GET /care/diagnosis/home`

```json
{
  "product": {
    "productId": "MCM001",
    "name": "Aren Crossbody",
    "material": "coated_cowhide",
    "color": "Cognac"
  },
  "currentSensor": {
    "temperature": 24.8,
    "humidity": 68.4,
    "measuredAt": "2026-08-16T09:40:00Z"
  },
  "movementSummary": {
    "motionTotal": 72,
    "activeWindowCount": 36,
    "maxShock": 0.34,
    "handlingLevel": "LOW"
  },
  "aiCareSummary": {
    "dataSufficiency": {},
    "productCondition": {},
    "stressLabels": {},
    "careDecision": {},
    "explanation": {}
  }
}
```

미수집 상태:

```json
{
  "currentSensor": {
    "temperature": null,
    "humidity": null,
    "measuredAt": null
  },
  "aiCareSummary": {
    "dataSufficiency": {
      "status": "INSUFFICIENT_DATA",
      "reason": "MIN_COVERAGE_HOURS_NOT_MET"
    },
    "productCondition": {
      "label": "Collecting Data",
      "score": null,
      "summary": "제품 상태 분석을 위해 데이터를 수집하고 있습니다."
    }
  }
}
```

## 7.3 상태 리포트: `GET /care/report?period=7d|30d`

```json
{
  "period": "7d",
  "product": {},
  "featureSummary": {
    "avgTemperature": 24.8,
    "avgHumidity": 56.4,
    "rhHoursGt65": 10.0,
    "leatherMouldDose": 0.0042,
    "motionTotal": 72,
    "activeDays": 2,
    "maxShock": 0.34
  },
  "aiCareSummary": {
    "productCondition": {},
    "stressLabels": {},
    "careDecision": {},
    "explanation": {
      "short": "최근 7일 동안 고습 노출이 일부 누적되었습니다.",
      "reasonBullets": [
        "고습 노출 시간이 확인되어 습도 관리 단계가 CAUTION으로 평가되었습니다.",
        "현재 점검이 필요한 증상은 보고되지 않았습니다."
      ]
    },
    "reservationCta": {}
  }
}
```

프론트 사용:

- `featureSummary`: 숫자 카드
- `stressLabels`: 상태 badge
- `explanation.reasonBullets`: 상태 해석 문구
- `reservationCta`: 케어 예약 CTA

## 7.4 환경 데이터 상세: `GET /care/environment?period=7d|30d|1y`

```json
{
  "period": "7d",
  "dataSufficiency": {},
  "series": {
    "temperature": [
      {
        "measuredAt": "2026-08-16T09:40:00Z",
        "value": 24.8
      }
    ],
    "humidity": [
      {
        "measuredAt": "2026-08-16T09:40:00Z",
        "value": 68.4
      }
    ]
  },
  "thresholdBands": {
    "humidity": [
      {
        "label": "Stable",
        "min": 45,
        "max": 55
      },
      {
        "label": "Caution",
        "min": 65,
        "max": null
      }
    ],
    "temperature": [
      {
        "label": "Warm Exposure",
        "min": 30,
        "max": null
      }
    ]
  },
  "featureSummary": {
    "avgTemperature": 24.8,
    "avgHumidity": 56.4,
    "rhHoursGt65": 10.0,
    "tempHoursAbove30": 0.0,
    "motionTotal": 72,
    "maxShock": 0.34
  },
  "interpretation": {
    "short": "그래프의 순간값보다 안정 범위를 벗어난 누적 시간이 관리 판단에 더 중요합니다.",
    "bullets": [
      "최근 기간 중 RH 65%를 넘은 시간이 10시간 확인되었습니다.",
      "이 값은 손상 확정이 아니라 예방 관리 알림 기준입니다."
    ]
  }
}
```

주의:

- 1년 데이터는 raw point가 많으므로 daily aggregate를 권장한다.

## 7.5 관리 가이드: `GET /care/guide?productId=...`

```json
{
  "product": {},
  "materialGuide": {
    "material": "coated_cowhide",
    "staticTips": [
      {
        "title": "습기 피하기",
        "description": "고습 환경에 장시간 보관하지 않는 것이 좋습니다."
      },
      {
        "title": "직접 열 피하기",
        "description": "드라이어, 라디에이터 등 직접 열로 말리지 마세요."
      }
    ]
  },
  "personalizedGuide": {
    "weeklyTip": "이번 주에는 보관 공간 환기를 우선 추천합니다.",
    "recommendedActions": [],
    "doNotDo": [],
    "inspectionWarning": "곰팡이 냄새, 물 얼룩, 표면 끈적임이 보이면 점검을 권장합니다."
  }
}
```

## 7.6 예약 CTA: 공통 블록

`reservationCta`는 `aiCareSummary` 안에 포함할 수 있다.

```json
{
  "reservationCta": {
    "recommended": true,
    "level": "RECOMMENDED",
    "title": "전문가 점검을 권장합니다",
    "description": "표면 증상이 확인되어 브랜드/전문가 점검을 받아보는 것이 좋습니다.",
    "suggestedServiceType": "condition_check",
    "prefillNote": "최근 습기 노출 이후 표면 상태 점검을 요청합니다."
  }
}
```

MVP 노출 기준:

| condition | level |
| --- | --- |
| `inspectionNeed = REQUIRED` | `REQUIRED` |
| `inspectionNeed = CONDITIONAL` | `RECOMMENDED` 또는 `OPTIONAL` |
| `careNeed = MEDIUM_HIGH/HIGH` | `OPTIONAL` |
| 그 외 | `NONE` |

## 8. LLM / Copy Generation 정책

MVP에서는 full free-form generation보다 template 기반 문구를 권장한다.

LLM을 쓰더라도 입력은 반드시 Rule Evaluator output으로 제한한다.

상세 Prompt 정책과 JSON 입출력 형식은 다음 문서를 따른다.

- `docs/06-llm-explanation.md`
- `data/llm-prompt-template.json`

LLM 금지:

- 손상 확률 생성
- 출처에 없는 threshold 생성
- 센서로 알 수 없는 증상 단정
- "가죽이 손상되었습니다" 같은 확정 표현

권장 표현:

```text
현재 데이터 기준 고습 노출이 일부 누적되었습니다.
손상이 확인된 것은 아니지만, 보관 환경을 조정하는 것이 좋습니다.
```

## 9. Extension Slots

추후 확장을 위해 다음 필드는 optional로 남겨둔다.

```json
{
  "aiCareSummary": {
    "evidence": {
      "matchedKbEntries": ["KB-001"],
      "triggeredRules": ["leather_sustained_rh_gt_65"],
      "sourceLevel": "A"
    },
    "weakSupervision": {
      "labelFunctions": ["LF_leather_rh65_sustained"],
      "syntheticScenarioId": null
    },
    "debug": {
      "featureVersion": "mxis-feature-extractor-v0.1",
      "ruleVersion": "care-model-v1.1-preventive-tier-draft"
    }
  }
}
```

MVP에서는 프론트에 표시하지 않는다.

## 10. Backend Implementation Priority

1. `aiCareSummary` 공통 블록 생성
2. `dataSufficiency` 구현
3. `productCondition.label/score/summary` 구현
4. `stressLabels` 구현
5. `careDecision.recommendedActions/doNotDo` 구현
6. `care/report`의 `featureSummary` 구현
7. `care/environment`의 `series`와 `thresholdBands` 구현
8. `care/guide`의 static + personalized guide 구현
9. `reservationCta` 구현
10. optional evidence/debug block 추가
