# MXIS Feature Extractor Spec v0.1

작성일: 2026-08-16

상태: MVP Draft

연결 문서:

- `MXIS Sensor Input Data Contract v0.1`
- `data/knowledge-base.json`
- `data/rule-spec.json`
- `prototype/mxis_rule_evaluator.py`

## 1. 목적

Feature Extractor는 Smart Charm의 `SensorReading` raw/window 데이터를 AI/Rule Engine이 사용할 수 있는 exposure feature로 변환한다.

```text
SensorReading Table
-> Feature Extractor
-> Exposure Features
-> Care-model-v1 Rule Evaluator
-> Care Report / AI Explanation
```

Feature Extractor는 손상 여부를 판단하지 않는다. 판단은 Rule Evaluator가 수행한다.

Feature Extractor의 책임:

- 시간 window 정렬
- missing/invalid reading 제거
- 온습도 노출 시간 계산
- leather mould dose 계산
- IMU handling exposure 계산
- data sufficiency 계산
- AI/Rule Engine input schema 생성

## 2. 입력 데이터

### 2.1 SensorReading Source

Smart Charm은 window 단위로 `SensorReading`을 생성한다.

운영 기준:

```text
window = 10분
```

개발 기준:

```text
window = 10초
```

서버 저장 DTO:

```json
{
  "sequence": 501,
  "measuredAt": 1735123456,
  "temperature": 24.77,
  "humidity": 68.52,
  "maxShock": 0.34,
  "motionCount": 12
}
```

### 2.2 Feature Extractor Input

```json
{
  "productId": "MCM001",
  "deviceId": "SC001",
  "materialId": "coated_cowhide",
  "materialSubtypes": ["grained_coated_cowhide"],
  "analysisWindowDays": 7,
  "samplingWindowSeconds": 600,
  "sensorReadings": [
    {
      "sequence": 501,
      "measuredAt": 1735123456,
      "temperature": 24.77,
      "humidity": 68.52,
      "maxShock": 0.34,
      "motionCount": 12
    }
  ],
  "userEvents": {
    "wetEventReported": false,
    "directHeatEventReported": false,
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
  }
}
```

## 3. SensorReading Field 해석

| field | unit | source | AI 해석 |
| --- | --- | --- | --- |
| `sequence` | count | device | 중복/누락/순서 검증 |
| `measuredAt` | Unix seconds | device | window timestamp. `0`이면 timestamp invalid |
| `temperature` | Celsius | SHT40 | window 종료 시점 온도 |
| `humidity` | %RH | SHT40 | window 종료 시점 상대습도 |
| `maxShock` | g | IMU derived | window 내 최대 dynamicAcceleration |
| `motionCount` | count | IMU derived | dynamicAcceleration >0.12g, cooldown 300ms 기준 event 수 |

주의:

- `maxShock`는 가방 손상 threshold가 아니다.
- `motionCount`는 외출/사용/움직임 proxy다.
- IMU raw x/y/z와 gyro 상세 패턴은 서버에 없다.

## 4. 분석 Window

기본 window:

| 목적 | window |
| --- | --- |
| 홈/케어 진단 기본 | 최근 7일 |
| 상태 리포트 기본 | 최근 30일 |
| 환경 데이터 상세 | 7일 / 30일 / 1년 |
| 첫 등록 직후 data sufficiency | 최소 24시간 |

Feature naming 규칙:

```text
{metric}_{condition}_{window}
```

예:

```text
rh_hours_gt_65_7d
temp_hours_above_30_7d
leather_mould_dose_30d
motion_total_7d
```

## 5. Preprocessing

### 5.1 Timestamp 처리

유효 reading:

```text
measuredAt > 0
temperature != null
humidity != null
```

`measuredAt = 0`:

- exposure duration 계산에서 제외
- `invalid_timestamp_count`에 포함
- data sufficiency에는 불리하게 반영

### 5.2 정렬

모든 reading은 다음 기준으로 정렬한다.

```text
deviceId ASC
measuredAt ASC
sequence ASC
```

### 5.3 중복 제거

동일 device에서 같은 `sequence`가 중복되면 하나만 사용한다.

권장 우선순위:

1. measuredAt이 유효한 reading
2. 서버 수신 시간이 더 빠른 reading
3. 동일하면 첫 reading 유지

### 5.4 Window Duration

권장 입력:

```json
{
  "samplingWindowSeconds": 600
}
```

없으면 MVP 운영 기본값:

```text
600 seconds
```

개발 환경에서는 10초 window가 가능하므로, feature extractor는 hard-code하지 말고 `samplingWindowSeconds`를 우선 사용한다.

### 5.5 Missing Data

Sensor Contract 기준:

- SHT40 실패: 해당 window는 생성하지 않음
- IMU 실패: `maxShock=0`, `motionCount=0`
- Time sync 전: `measuredAt=0`

AI 관점 추가 정책:

| 상황 | 처리 |
| --- | --- |
| SHT40 missing | reading 없음. coverage 감소 |
| IMU missing | 현재는 inactivity와 구분 불가 |
| measuredAt=0 | exposure 계산 제외 |
| temperature only missing | invalid environmental reading |
| humidity only missing | invalid environmental reading |

향후 `sensorErrorCode`가 추가되면 IMU failure와 genuine inactivity를 분리한다.

## 6. Data Sufficiency

MVP 최소 조건:

| 항목 | 기준 |
| --- | --- |
| valid SensorReading | 최소 24개 |
| coverage | 24시간 이상 |
| temperature | 존재 |
| humidity | 존재 |

주의:

- 운영 window 10분 기준 24시간 coverage는 약 144개 reading이다.
- 따라서 24개 reading은 단독 충분 조건이 아니다.

### 6.1 Coverage 계산

```text
coverage_hours =
  (max(measuredAt) - min(measuredAt)) / 3600
  + samplingWindowSeconds / 3600
```

### 6.2 Data Sufficiency Output

```json
{
  "status": "SUFFICIENT",
  "reason": null,
  "validReadingCount": 144,
  "requiredReadingCount": 24,
  "coverageHours": 24.0,
  "requiredCoverageHours": 24,
  "invalidTimestampCount": 0,
  "lastMeasuredAt": 1735209856
}
```

가능한 status:

| status | 의미 |
| --- | --- |
| `SUFFICIENT` | AI 분석 가능 |
| `INSUFFICIENT_DATA` | 최소 조건 미달 |
| `STALE_DATA` | 마지막 sync/measurement가 오래됨 |
| `NO_DATA` | 유효 reading 없음 |

가능한 reason:

- `NO_VALID_READING`
- `MIN_READING_COUNT_NOT_MET`
- `MIN_COVERAGE_HOURS_NOT_MET`
- `MISSING_TEMPERATURE`
- `MISSING_HUMIDITY`
- `STALE_LAST_SYNC`

## 7. Environment Features

### 7.1 Basic Statistics

분석 window별로 계산한다.

| feature | unit | formula |
| --- | --- | --- |
| `avg_temperature_c_{window}` | C | average temperature |
| `max_temperature_c_{window}` | C | max temperature |
| `min_temperature_c_{window}` | C | min temperature |
| `avg_humidity_rh_{window}` | %RH | average humidity |
| `max_humidity_rh_{window}` | %RH | max humidity |
| `min_humidity_rh_{window}` | %RH | min humidity |

예:

```text
avg_temperature_c_7d
max_humidity_rh_30d
```

### 7.2 RH Exposure Features

Leather 기준:

| feature | threshold | unit | 근거 |
| --- | --- | --- | --- |
| `rh_hours_gt_65_{window}` | RH >65% | hours | CCI leather caution/action threshold |
| `rh_hours_gt_70_{window}` | RH >=70% | hours | CCI mould time band lower point |
| `rh_hours_gt_80_{window}` | RH >=80% | hours | CCI mould time band |
| `rh_hours_gt_90_{window}` | RH >=90% | hours | CCI mould time band |
| `rh_hours_lt_30_{window}` | RH <30% | hours | CCI leather dryness threshold |

Canvas/textile 기준:

| feature | threshold | unit | 근거 |
| --- | --- | --- | --- |
| `rh_hours_gt_70_{window}` | RH >=70% | hours | CCI textile damp condition |
| `rh_hours_gt_80_stagnant_{window}` | RH >=80% + stagnant flag | hours | Smithsonian mould context |
| `rh_hours_lt_37_{window}` | RH <37% | hours | Smithsonian 45% +/-8 lower bound |

계산식:

```text
rh_hours_gt_65 =
  count(valid readings where humidity >65)
  * samplingWindowSeconds / 3600
```

timestamp 간격이 불규칙하면:

```text
duration_i = min(nextMeasuredAt - measuredAt, maxGapCap)
```

MVP에서는 window duration이 고정되어 있으므로 `samplingWindowSeconds` 기반 계산을 우선한다.

### 7.3 Leather Mould Dose

CCI leather mould time band 기반 normalized dose:

```text
leather_mould_dose =
  hours_at_90_or_more / 48
+ hours_at_80_to_90 / 240
+ hours_at_70_to_80 / 2400
```

해석:

| value | tier use | 의미 |
| --- | --- | --- |
| `<0.1` | no direct tier rise | source-backed mould band에 거의 접근하지 않음 |
| `>=0.1` | `ELEVATED` candidate | damage-supporting band에 부분 접근 |
| `>=1.0` | `HIGH` candidate | source-backed damage-supporting exposure band 도달 |

주의:

- 곰팡이 발생 확률이 아니다.
- 오염, 통풍, 표면 상태, 소재 finish에 따라 실제 결과는 달라진다.

### 7.4 Temperature Exposure Features

| feature | threshold | unit | 의미 |
| --- | --- | --- | --- |
| `temp_hours_above_30_{window}` | temperature >30C | hours | warm exposure candidate |
| `temp_hours_above_40_{window}` | temperature >40C | hours | extreme exposure candidate |
| `temp_hours_above_23_3_{window}` | temperature >23.3C | hours | textile/canvas Smithsonian upper target |

주의:

- `30C`, `40C`는 가방 손상 온도가 아니다.
- 보존/박물관 기준과 일상 사용 사이의 예방 exposure band다.

### 7.5 Warm-Moist Exposure

Natural/vegetable-tanned leather는 warm + moist combination에 민감하게 본다.

MVP feature:

```text
warm_moist_exposure_hours_{window} =
  hours where humidity >65% AND temperature >30C
```

향후 beta 데이터가 쌓이면 temperature threshold와 duration band를 보정한다.

## 8. IMU / Handling Features

SensorReading에서 제공되는 IMU-derived fields:

- `maxShock`
- `motionCount`

### 8.1 Motion Features

| feature | unit | formula |
| --- | --- | --- |
| `motion_total_{window}` | count | sum(motionCount) |
| `motion_avg_per_active_window_{window}` | count/window | motion_total / active_window_count |
| `active_window_count_{window}` | count | count(motionCount >= 1) |
| `inactive_window_count_{window}` | count | valid windows - active windows |
| `active_window_ratio_{window}` | ratio | active_window_count / valid windows |

### 8.2 Shock Features

| feature | unit | formula |
| --- | --- | --- |
| `max_shock_g_{window}` | g | max(maxShock) |
| `avg_max_shock_g_{window}` | g | average(maxShock) |
| `shock_windows_gt_1g_{window}` | count | count(maxShock >=1.0) |
| `shock_windows_gt_2g_{window}` | count | count(maxShock >=2.0) |

주의:

- `1g`, `2g`는 손상 threshold가 아니다.
- handling intensity candidate다.
- 실제 제품 손상 판단은 visible symptom 또는 user report와 결합해야 한다.

### 8.3 Usage Pattern Proxy

외출/사용 횟수는 직접 측정되지 않는다. MVP에서는 motion pattern proxy로만 추정한다.

초안:

```text
active_day =
  해당 날짜에 active_window_count >= active_day_min_windows
```

MVP 기본값:

```text
active_day_min_windows = 3
```

생성 feature:

| feature | unit | description |
| --- | --- | --- |
| `active_days_{window}` | days | active_day count |
| `inactive_days_{window}` | days | no active window days |
| `consecutive_active_days` | days | 연속 active day |
| `consecutive_inactive_days` | days | 연속 inactive day |

주의:

- active day는 외출 횟수와 동일하지 않다.
- 사용자가 가방을 움직이지 않고 보관해도 sensor movement가 낮을 수 있다.
- 반대로 가방이 이동 중 흔들렸다고 실제 외출/사용이라고 단정할 수 없다.

## 9. User Event / Symptom Merge

Feature Extractor는 sensor feature와 user input을 병합해 Rule Engine input을 만든다.

Sensor로 알 수 없는 것:

- 물 접촉 여부
- 직사광선 노출 여부
- 곰팡이 육안 확인
- 냄새
- 물 얼룩
- 코팅 끈적임
- 갈라짐
- suede nap matting

따라서 아래 user input은 별도 필드로 유지한다.

```json
{
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
  }
}
```

## 10. Feature Extractor Output Schema

```json
{
  "productId": "MCM001",
  "deviceId": "SC001",
  "materialId": "coated_cowhide",
  "materialSubtypes": ["grained_coated_cowhide"],
  "analysisWindowDays": 7,
  "generatedAt": "2026-08-16T09:41:00Z",
  "dataSufficiency": {
    "status": "SUFFICIENT",
    "reason": null,
    "validReadingCount": 144,
    "coverageHours": 24.0,
    "invalidTimestampCount": 0,
    "lastMeasuredAt": 1735209856
  },
  "environmentFeatures": {
    "avgTemperatureC7d": 24.8,
    "maxTemperatureC7d": 30.1,
    "avgHumidityRh7d": 56.4,
    "maxHumidityRh7d": 68.4,
    "rhHoursGt657d": 10.0,
    "rhHoursLt307d": 0.0,
    "leatherMouldDose7d": 0.0042,
    "tempHoursAbove307d": 0.0,
    "warmMoistExposureHours7d": 0.0
  },
  "handlingFeatures": {
    "motionTotal7d": 72,
    "activeWindowCount7d": 36,
    "inactiveWindowCount7d": 108,
    "activeWindowRatio7d": 0.25,
    "maxShockG7d": 0.34,
    "shockWindowsGt2g7d": 0,
    "activeDays7d": 2,
    "consecutiveActiveDays": 1
  },
  "userEvents": {},
  "userSymptoms": {}
}
```

## 11. Rule Evaluator Input Mapping

Feature Extractor output은 Rule Evaluator에 다음처럼 매핑된다.

| Feature Extractor | Rule Evaluator |
| --- | --- |
| `rhHoursGt657d` | `rh_hours_gt_65_7d` |
| `rhHoursGt6530d` | `rh_hours_gt_65_30d` |
| `rhHoursLt307d` | `rh_hours_lt_30_7d` |
| `leatherMouldDose7d` | `leather_mould_dose_7d` |
| `tempHoursAbove307d` | `temp_hours_above_30_7d` |
| `tempHoursAbove407d` | `temp_hours_above_40_7d` |
| `warmMoistExposureHours7d` | `warm_moist_exposure_hours_7d` |
| `motionTotal7d` | `motion_total_7d` |
| `activeWindowCount7d` | `active_window_count_7d` |
| `maxShockG7d` | `imu_max_accel_g_7d` |

권장:

- 백엔드 내부는 snake_case 사용
- API response는 프론트 컨벤션에 따라 camelCase 가능
- AI/Rule Engine config는 snake_case 유지

## 12. Quality Flags

AI response에는 feature와 함께 품질 flag를 내려야 한다.

| flag | 의미 |
| --- | --- |
| `hasEnoughCoverage` | 24시간 이상 coverage |
| `hasEnoughReadings` | 최소 reading 수 충족 |
| `hasRecentSync` | 최근 sync 기준 충족 |
| `hasTimestampGaps` | timestamp gap 존재 |
| `hasInvalidTimestamps` | measuredAt=0 존재 |
| `imuFailureUnknown` | IMU failure와 inactivity 구분 불가 |
| `lightUnavailable` | light/UV 센서 없음 |

## 13. Weak Supervision Synthetic Feature 생성

Synthetic dataset은 `SensorReading` 단위로 생성한다.

### 13.1 Stable Storage

```text
temperature: 18-25C
humidity: 45-55% RH
maxShock: 0-0.2g
motionCount: 0-2
```

expected:

```text
humidity LOW
dryness LOW
handling LOW
```

### 13.2 Sustained High Humidity

```text
humidity >65% for 8h
```

expected:

```text
humidity CAUTION
```

### 13.3 Mould Dose Approach

```text
humidity 80-90% for 24h
```

expected:

```text
humidity ELEVATED
```

### 13.4 Mould Dose Reached

```text
humidity >=90% for 48h
```

expected:

```text
humidity HIGH
```

### 13.5 Dry Leather Exposure

```text
humidity <30% sustained
```

expected:

```text
dryness CAUTION
```

### 13.6 Active Handling Day

```text
motionCount elevated across multiple windows
maxShock occasionally high
```

expected:

```text
handling CAUTION
```

주의:

- IMU synthetic label은 손상 label이 아니라 handling exposure label이다.

## 14. Open Questions

1. 운영 window는 항상 10분으로 고정되는가?
2. `samplingWindowSeconds`를 upload payload 또는 device config API로 제공할 것인가?
3. `motionCount` 기준인 `0.12g`, cooldown `300ms`는 firmware에서 버전 관리되는가?
4. IMU failure와 genuine inactivity를 구분하기 위한 `sensorErrorCode`는 언제 추가되는가?
5. `active_day_min_windows = 3` 기준은 제품팀/데이터팀에서 받아들일 수 있는가?
6. `lastSyncedAt` stale 기준은 10분, 30분, 24시간 중 어떤 UX 상태와 연결할 것인가?
7. 1년 환경 데이터는 raw reading 기반으로 유지할 것인가, daily aggregate로 보관할 것인가?

## 15. Implementation Priority

1. SensorReading -> feature 변환 함수 구현
2. data sufficiency block 구현
3. 7d/30d feature 계산
4. leather mould dose 계산
5. motion/active window feature 계산
6. Rule Evaluator input adapter 구현
7. synthetic SensorReading generator 구현
8. AI Output Contract와 연결
