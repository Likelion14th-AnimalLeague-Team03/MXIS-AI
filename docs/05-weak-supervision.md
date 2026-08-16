# MXIS Weak Supervision Synthetic Dataset Spec v0.1

작성일: 2026-08-17

상태: MVP Draft

## 1. 목적

실제 손상/점검/수리 label이 부족한 초기 단계에서, 검증된 Knowledge Base와 일상 사용 시나리오를 결합해 Rule Evaluator와 AI 문구를 검증할 synthetic dataset을 생성한다.

```text
Scenario
-> Synthetic SensorReading[]
-> Feature Extractor
-> Rule Evaluator
-> Weak Label + Provenance
-> Dataset
```

이 데이터셋은 초기 ML 손상 예측용 정답 데이터가 아니다. MVP에서는 다음 용도로 사용한다.

- Rule Evaluator 회귀 테스트
- 프론트 상태/문구 검증
- LLM explanation prompt 검증
- weak label function 충돌 확인
- 향후 실제 데이터 라벨링 설계 기준

## 2. Case Schema

```json
{
  "caseId": "SYN-0001",
  "scenario": "sustained_high_humidity",
  "materialId": "coated_cowhide",
  "materialSubtypes": [],
  "samplingWindowSeconds": 600,
  "analysisWindowDays": 7,
  "sensorReadings": [],
  "userEvents": {},
  "userSymptoms": {},
  "featureOutput": {},
  "ruleOutput": {},
  "weakLabels": {
    "stressLabels": {
      "humidity": "CAUTION"
    },
    "careNeed": "LOW_MEDIUM",
    "inspectionNeed": "NONE"
  },
  "labelSources": [
    "LF_leather_rh65_sustained",
    "KB-001"
  ]
}
```

## 3. MVP Scenario 목록

| scenario | 목적 | 대표 weak label |
| --- | --- | --- |
| `stable_storage` | 안정 보관 기준 | all `LOW` |
| `sustained_high_humidity` | RH >65% 지속 | humidity `CAUTION` |
| `mould_dose_approach` | CCI mould band 부분 접근 | humidity `ELEVATED` |
| `mould_dose_reached` | CCI mould band 도달 | humidity `HIGH` |
| `dry_leather_exposure` | RH <30% 지속 | dryness `CAUTION` |
| `warm_moist_sensitive_leather` | natural/vachetta warm+moist | heat/humidity `ELEVATED` |
| `active_handling_day` | 움직임 많은 날 | handling `CAUTION` |
| `shock_heavy_windows` | maxShock 높은 window | handling `CAUTION` |
| `insufficient_data` | 데이터 부족 | data sufficiency `INSUFFICIENT_DATA` |
| `timestamp_missing` | measuredAt=0 포함 | invalid timestamp |
| `wet_event_sensitive_material` | natural/suede 물 접촉 | humidity `ELEVATED` |
| `visible_mould_reported` | 증상 hard trigger | `INSPECTION_REQUIRED` |
| `suede_wet_nap_matting` | suede wet + nap symptom | `INSPECTION_REQUIRED` |
| `coated_finish_tacky` | coating hard trigger | `INSPECTION_REQUIRED` |

## 4. Label Function 원칙

Label function은 검증 근거 또는 운영 기준을 명시해야 한다.

예:

```text
LF_leather_rh65_sustained
IF material is leather-like AND rh_hours_gt_65_7d >= 8h
THEN humidity = CAUTION
source = CCI leather RH caution/action threshold
```

충돌 해결:

1. `INSPECTION_REQUIRED` hard trigger 우선
2. `HIGH` source-backed damage-supporting exposure
3. `ELEVATED` 반복/복합/민감 소재 이벤트
4. `CAUTION` 예방 알림
5. `LOW`

## 5. Synthetic SensorReading 생성 원칙

Sensor contract에 맞춰 raw IMU waveform이 아니라 window-level `SensorReading`을 생성한다.

```json
{
  "sequence": 1,
  "measuredAt": 1735123456,
  "temperature": 24.8,
  "humidity": 52.0,
  "maxShock": 0.12,
  "motionCount": 0
}
```

운영 기본값:

- `samplingWindowSeconds = 600`
- 24시간 sufficient case = 144 readings
- 7일 full case = 1008 readings

MVP dataset은 파일 크기를 줄이기 위해 대부분 24-48시간 규모로 생성하고, `analysisWindowDays=7`에 넣는다.

## 6. 출력 파일

Generator는 다음 파일을 생성한다.

- `tests/fixtures/synthetic-dataset.sample.json`
- optional: `tests/fixtures/synthetic-dataset.summary.json`

각 case에는 `featureOutput`과 `ruleOutput`을 포함해 end-to-end 확인이 가능해야 한다.
