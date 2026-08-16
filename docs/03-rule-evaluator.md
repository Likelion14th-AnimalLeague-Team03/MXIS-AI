# MXIS Care-model-v1 Rule Spec

작성일: 2026-08-16

버전: `care-model-v1.1-preventive-tier-draft`

연결 KB: `data/knowledge-base.json`, `data/material-risk-matrix.tsv`

## 1. 목적

Care-model-v1은 MXIS 럭셔리 가방 AI 케어 서비스의 첫 번째 deterministic rule/scoring engine이다.

이 모델의 목적은 손상 확률을 예측하는 것이 아니라, 센서/사용자 입력을 근거 기반 care decision으로 변환하는 것이다.

```text
Raw sensor/user event
-> Exposure feature
-> Material-aware stress label
-> Care action
-> Inspection decision
-> LLM explanation
```

v1에서 금지하는 출력:

- `mould risk = 0.18`
- `cracking probability = 23%`
- 근거 없는 shock g-force threshold
- 근거 없는 "며칠 사용 후 휴식" threshold

v1에서 허용하는 출력:

- `moisture-related degradation exposure: CAUTION`
- `dryness stress: ELEVATED`
- `inspection_need: CONDITIONAL`
- `recommended_actions: dry_at_room_temperature, avoid_direct_heat`

v1.1의 핵심 변경점:

- 논문/보존자료의 손상 발생 또는 mould-supporting 조건은 후행 경계로 사용한다.
- 럭셔리 가방 서비스에서는 변형이 일어나기 전에 `CAUTION`과 `ELEVATED` 단계에서 예방 행동을 권장한다.
- `HIGH`는 damage-supporting exposure band에 가까운 강한 노출이며, 실제 손상 확정은 아니다.
- `INSPECTION_REQUIRED`는 센서값 단독이 아니라 visible symptom 또는 hard trigger 중심으로 반환한다.

## 2. Scope

### 2.1 Materials

v1의 primary material은 다음 4개다.

- `coated_cowhide`
- `natural_leather`
- `suede`
- `canvas`

추가 subtype은 modifier로 관리한다.

| subtype | parent material | 주요 modifier |
| --- | --- | --- |
| `grained_coated_cowhide` | `coated_cowhide` | 일반 coated leather 기준 |
| `smooth_coated_cowhide` | `coated_cowhide` | scratch/abrasion 민감도 상향 가능 |
| `patent_or_glossy_finish` | `coated_cowhide` | tacky coating, colour transfer trigger 강화 |
| `vachetta` | `natural_leather` | water stain, oil stain, uneven patina 민감도 상향 |
| `vegetable_tanned_cowhide` | `natural_leather` | warm/moist, dryness 민감도 상향 |
| `nubuck` | `suede` | nap damage, water mark 민감도 상향 |
| `plain_canvas` | `canvas` | textile RH/light 기준 우선 |
| `coated_canvas` | `canvas` | coating tackiness/peel trigger 추가 |
| `printed_canvas` | `canvas` | print abrasion/fading trigger 추가 |
| `canvas_with_leather_trim` | `canvas` | leather trim threshold도 병합 |

### 2.2 Risk Factors

- `humidity`
- `temperature_heat`
- `dryness`
- `uv_light`
- `physical_shock_abrasion`
- `continuous_usage_rest`

## 3. Input Contract

Care-model-v1은 다음 입력을 받는다.

```json
{
  "item_id": "string",
  "material_id": "natural_leather",
  "material_subtypes": ["vachetta"],
  "sensor_window": {
    "rh_readings": [],
    "temperature_readings": [],
    "light_readings": [],
    "motion_events": []
  },
  "user_events": {
    "wet_event_reported": false,
    "direct_heat_event_reported": false,
    "direct_sun_exposure_reported": false,
    "abrasive_contact_event": false,
    "overload_reported": false
  },
  "user_symptoms": {
    "visible_mould_reported": false,
    "musty_odour_reported": false,
    "water_stain_reported": false,
    "sticky_or_tacky_coating_reported": false,
    "cracking_reported": false,
    "stiffness_reported": false,
    "nap_matting_reported": false,
    "dye_transfer_reported": false,
    "corner_wear_reported": false,
    "shape_collapse_reported": false
  },
  "usage_log": {
    "usage_days_7d": 0,
    "usage_days_30d": 0,
    "rest_days_30d": 0
  }
}
```

## 4. Feature Dictionary

### 4.1 Environment Features

| feature | type | unit | description | source |
| --- | --- | --- | --- | --- |
| `rh_hours_gt_65_7d` | number | hours | 최근 7일 RH >65% 누적 시간. leather 고습 stress 후보 | sensor |
| `rh_hours_gt_65_30d` | number | hours | 최근 30일 RH >65% 누적 시간 | sensor |
| `rh_hours_gt_70_7d` | number | hours | 최근 7일 RH >70% 누적 시간. textile/canvas damp condition 후보 | sensor |
| `rh_hours_gt_80_stagnant_7d` | number | hours | stagnant air 조건에서 RH >80% 누적 시간 | sensor + ventilation proxy |
| `rh_hours_lt_30_7d` | number | hours | 최근 7일 RH <30% 누적 시간. leather dryness 후보 | sensor |
| `rh_hours_lt_30_30d` | number | hours | 최근 30일 RH <30% 누적 시간 | sensor |
| `rh_hours_lt_37_30d` | number | hours | 최근 30일 RH <37% 누적 시간. textile lower-bound 후보 | sensor |
| `warm_moist_exposure_hours_7d` | number | hours | 고습과 높은 온도가 동시에 나타난 시간 | derived |
| `temp_hours_above_local_comfort_7d` | number | hours | leather 권장 범위를 벗어난 고온 노출 proxy. v1에서는 보조 feature | sensor |
| `temp_hours_above_23_3_7d` | number | hours | textile/canvas Smithsonian upper target 초과 시간 | sensor |
| `direct_heat_event_reported` | boolean | - | radiator, dryer, hot car, direct heat source 이벤트 | user |
| `direct_sun_exposure_hours_7d` | number | hours | 직사광선 노출 추정 시간 | sensor/user |
| `lux_hours_estimate_30d` | number | lux-hours | 30일 누적 light exposure 추정 | sensor |
| `uv_exposure_proxy` | number/string | index | UV 센서 또는 sunlight proxy | sensor/derived |

### 4.2 Use and Handling Features

| feature | type | unit | description | source |
| --- | --- | --- | --- | --- |
| `wet_event_reported` | boolean | - | 비, 물 튐, 젖음 이벤트 | user |
| `abrasive_contact_event` | boolean | - | rough surface/floor/hard contact 이벤트 | user |
| `imu_energetic_event_count_7d` | integer | count | 최근 7일 `maxShock`가 운영상 energetic 기준을 넘은 window 수. 손상 threshold가 아니라 handling exposure proxy | sensor |
| `imu_max_accel_g_7d` | number | g | 최근 7일 window-level 최대 dynamic acceleration | sensor |
| `motion_total_7d` | integer | count | 최근 7일 `motionCount` 누적. 사용/마찰 노출의 약한 proxy | sensor |
| `active_window_count_7d` | integer | count | `motionCount >= 1`인 window 수. 지속 사용 proxy | sensor |
| `overload_reported` | boolean | - | 과적재/무거운 내용물 보고 | user |
| `usage_days_7d` | integer | days | 최근 7일 사용일 | usage |
| `usage_days_30d` | integer | days | 최근 30일 사용일 | usage |
| `rest_days_30d` | integer | days | 최근 30일 휴식일 | usage |
| `post_use_wipe_confirmed` | boolean | - | 사용 후 닦음 여부 | user |
| `post_use_brush_confirmed` | boolean | - | suede dry brushing 여부 | user |

### 4.3 Symptom Features

| feature | type | description |
| --- | --- | --- |
| `visible_mould_reported` | boolean | 곰팡이 육안 확인 |
| `musty_odour_reported` | boolean | 곰팡이/습기 냄새 |
| `water_stain_reported` | boolean | 물 얼룩 |
| `sticky_or_tacky_coating_reported` | boolean | 코팅 끈적임/표면 tackiness |
| `blistering_reported` | boolean | 코팅 부풀음 |
| `cracking_reported` | boolean | 갈라짐 |
| `stiffness_reported` | boolean | 경화/뻣뻣함 |
| `powdery_surface_reported` | boolean | 분말화/가루짐 |
| `nap_matting_reported` | boolean | suede nap 눌림/뭉침 |
| `nap_loss_reported` | boolean | suede nap 손실 |
| `dye_transfer_reported` | boolean | 이염/색상 전이 |
| `corner_wear_reported` | boolean | 모서리 마모 |
| `deep_scratch_reported` | boolean | 깊은 스크래치 |
| `handle_strain_reported` | boolean | 핸들/스트랩 장력 손상 |
| `shape_collapse_reported` | boolean | 형태 무너짐 |

## 5. Stress Labels

각 risk factor는 다음 label 중 하나를 반환한다.

| label | meaning | user-facing wording |
| --- | --- | --- |
| `LOW` | 특별한 노출/증상 없음 | 안정적 |
| `CAUTION` | 안정 범위를 벗어난 짧은/지속 노출 또는 관리 습관 보정 필요 | 주의 |
| `ELEVATED` | 반복 노출, 민감 소재와 직접 이벤트의 결합, 또는 damage-supporting band에 부분 접근 | 관리 필요 |
| `HIGH` | 출처 기반 damage-supporting exposure band에 도달하거나 매우 강한 노출 | 강한 관리 필요 |
| `INSPECTION_REQUIRED` | 증상 또는 고위험 trigger가 있어 전문가/브랜드 점검 우선 | 점검 권장 |
| `UNKNOWN` | 입력 부족 | 판단 보류 |

v1에서 stress label은 손상 확률이 아니다. `CAUTION`은 예방 알림, `ELEVATED`는 반복/복합 노출 관리 단계, `HIGH`는 damage-supporting condition에 가까운 강한 노출이다. 실제 손상 확정은 visible symptom이나 inspection trigger로만 다룬다.

## 6. Material Sensitivity Modifiers

| material/subtype | humidity | dryness | heat | light | abrasion | water_stain | notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `coated_cowhide` | normal | normal | normal | normal | normal | medium | coating symptom trigger 중요 |
| `patent_or_glossy_finish` | normal | normal | high | high | high | medium | tacky/coating transfer trigger 강화 |
| `natural_leather` | high | high | high | high | high | high | 물/오일/손소독제 이벤트 중요 |
| `vachetta` | very_high | high | high | high | high | very_high | water stain, uneven patina 강화 |
| `suede` | high | normal | high | high | high | high | nap-related trigger 강화 |
| `nubuck` | high | normal | high | high | high | high | suede와 동일하게 시작 |
| `canvas` | normal | low | normal | high | normal | medium | subtype flag 필요 |
| `coated_canvas` | normal | low | high | high | high | medium | coating/print symptom trigger 강화 |
| `printed_canvas` | normal | low | normal | high | high | medium | print abrasion/fading 강화 |
| `canvas_with_leather_trim` | high | high | normal | high | normal | high | leather trim 기준 병합 |

## 7. Rule Priority

판정 순서는 다음을 따른다.

1. `INSPECTION_REQUIRED` hard trigger
2. Material-specific symptom trigger
3. Direct event trigger
4. Threshold breach
5. Repetition/cumulative exposure
6. Usage/rest and care habit modifier
7. Default `LOW` or `UNKNOWN`

증상이 있는 경우 sensor threshold보다 증상을 우선한다. 예를 들어 `visible_mould_reported = true`이면 RH 기록이 낮아도 inspection 우선이다.

## 8. Inspection Trigger Codebook

| trigger_code | condition | severity | applicable materials | decision |
| --- | --- | --- | --- | --- |
| `visible_mould` | `visible_mould_reported = true` | hard | all | `INSPECTION_REQUIRED` |
| `musty_odour_after_humidity` | `musty_odour_reported = true` and humidity stress not `LOW` | hard | all | `INSPECTION_REQUIRED` |
| `water_stain_natural_or_suede` | `water_stain_reported = true` | hard | `natural_leather`, `suede` | `INSPECTION_REQUIRED` |
| `sticky_tacky_coating` | `sticky_or_tacky_coating_reported = true` | hard | `coated_cowhide`, `coated_canvas`, `patent_or_glossy_finish` | `INSPECTION_REQUIRED` |
| `blistering_after_moisture` | `blistering_reported = true` | hard | `coated_cowhide`, `coated_canvas` | `INSPECTION_REQUIRED` |
| `active_cracking` | `cracking_reported = true` | hard | leather, canvas trim | `INSPECTION_REQUIRED` |
| `powdery_surface` | `powdery_surface_reported = true` | hard | leather | `INSPECTION_REQUIRED` |
| `nap_matting_after_wet` | `nap_matting_reported = true` and `wet_event_reported = true` | hard | `suede`, `nubuck` | `INSPECTION_REQUIRED` |
| `heavy_dye_transfer` | `dye_transfer_reported = true` | conditional | all | `CONDITIONAL` or `INSPECTION_REQUIRED` |
| `deep_corner_wear` | `corner_wear_reported = true` and severe user rating | conditional | all | `CONDITIONAL` |
| `handle_strain` | `handle_strain_reported = true` | hard | all | `INSPECTION_REQUIRED` |
| `shape_collapse` | `shape_collapse_reported = true` | conditional | all | `CONDITIONAL` |

## 9. Care Action Codebook

| action_code | user-facing meaning | constraints |
| --- | --- | --- |
| `blot_with_lint_free_cloth` | 부드러운 보풀 없는 천으로 물기를 눌러 제거 | 문지르지 않음 |
| `dry_at_room_temperature` | 실온에서 자연 건조 | direct heat 금지 |
| `avoid_direct_heat` | 드라이어, 라디에이터, 차량 내부 열 피하기 | 모든 소재 |
| `avoid_direct_sunlight` | 직사광선/창가 장시간 노출 피하기 | 모든 소재 |
| `store_in_dust_bag` | dust bag/cover에 보관 | 통기성 고려 |
| `support_shape_in_storage` | tissue/bubble support로 형태 유지 | 과도한 압축 금지 |
| `avoid_desiccant_for_leather` | leather에 일반 제습제/anti-humidity sachet 권장 금지 | Hermes 근거 |
| `ventilate_storage_area` | 보관 공간 환기| mould/odour 조건 |
| `wipe_after_use_soft_dry_cloth` | 사용 후 부드러운 마른 천으로 표면 먼지 제거 | suede 제외 또는 주의 |
| `brush_suede_gently_when_dry` | suede가 마른 상태에서 전용 brush로 가볍게 정리 | 젖은 상태 금지 |
| `avoid_abrasive_surfaces` | 거친 표면/바닥/마찰 피하기 | 모든 소재 |
| `avoid_overpacking` | 과적재 피하기 | 모든 소재 |
| `rotate_usage` | 사용을 주기적으로 분산 | exact day threshold 없음 |
| `avoid_oils_perfumes_sanitizers` | 오일, 향수, 화장품, 손소독제 접촉 피하기 | natural leather 우선 |
| `escalate_to_brand_or_specialist` | 브랜드/전문가 점검 권장 | hard trigger 발생 시 |

## 10. Stress Rule Draft

### 10.1 Humidity Rules

Leather materials: `coated_cowhide`, `natural_leather`, `suede`

```text
IF visible_mould_reported
  -> humidity_stress = INSPECTION_REQUIRED

ELSE IF musty_odour_reported AND rh_hours_gt_65_7d > 0
  -> humidity_stress = INSPECTION_REQUIRED

ELSE IF wet_event_reported AND material in [natural_leather, suede, vachetta, nubuck]
  -> humidity_stress = ELEVATED
  -> inspection_need = CONDITIONAL

ELSE IF wet_event_reported
  -> humidity_stress = CAUTION

ELSE IF leather_mould_dose >= 1.0
  -> humidity_stress = HIGH

ELSE IF leather_mould_dose >= 0.1
  -> humidity_stress = ELEVATED

ELSE IF rh_hours_gt_65_7d reaches sustained exposure band
  -> humidity_stress = CAUTION

ELSE IF rh_hours_gt_65_30d reaches repeated exposure band
  -> humidity_stress = ELEVATED

ELSE
  -> humidity_stress = LOW
```

Canvas:

```text
IF visible_mould_reported OR musty_odour_reported
  -> humidity_stress = INSPECTION_REQUIRED

ELSE IF rh_hours_gt_80_stagnant_7d > 0
  -> humidity_stress = ELEVATED

ELSE IF rh_hours_gt_70_7d > 0 OR wet_event_reported
  -> humidity_stress = CAUTION

ELSE
  -> humidity_stress = LOW
```

주의: v1.1에서는 순간값을 최종 제품 threshold로 고정하지 않는다. RH threshold breach는 duration feature로 계산하고, CCI leather mould time band는 `leather_mould_dose`로 별도 반영한다.

### 10.2 Dryness Rules

Leather materials:

```text
IF cracking_reported OR powdery_surface_reported
  -> dryness_stress = INSPECTION_REQUIRED

ELSE IF stiffness_reported AND rh_hours_lt_30_7d > 0
  -> dryness_stress = ELEVATED

ELSE IF rh_hours_lt_30_30d > 0
  -> dryness_stress = CAUTION

ELSE
  -> dryness_stress = LOW
```

Canvas:

```text
IF canvas_with_leather_trim AND cracking_reported
  -> dryness_stress = INSPECTION_REQUIRED

ELSE IF rh_hours_lt_37_30d > 0 AND brittle_fabric_or_trim_symptom
  -> dryness_stress = CAUTION

ELSE
  -> dryness_stress = LOW
```

### 10.3 Temperature/Heat Rules

```text
IF direct_heat_event_reported AND symptom in [stiffness, cracking, sticky_or_tacky_coating, blistering, warping]
  -> heat_stress = INSPECTION_REQUIRED

ELSE IF direct_heat_event_reported
  -> heat_stress = ELEVATED

ELSE IF warm_moist_exposure_hours_7d > 0 AND material in [natural_leather, vachetta, vegetable_tanned_cowhide]
  -> heat_stress = ELEVATED

ELSE IF temp threshold breach exists
  -> heat_stress = CAUTION

ELSE
  -> heat_stress = LOW
```

### 10.4 UV/Light Rules

```text
IF fading_or_yellowing_reported AND direct_sun_exposure_hours_7d > 0
  -> light_stress = ELEVATED or INSPECTION_REQUIRED if severe

ELSE IF direct_sun_exposure_hours_7d > 0 AND material light sensitivity is high
  -> light_stress = ELEVATED

ELSE IF lux_hours_estimate_30d suggests prolonged exposure
  -> light_stress = CAUTION

ELSE
  -> light_stress = LOW
```

v1에서는 lux-hours 기준값을 확정하지 않는다. 보존 threshold는 display/storage 기준이므로, beta validation 전까지는 `prolonged exposure` 판정에 보수적으로 사용한다.

### 10.5 Physical Shock/Abrasion Rules

```text
IF handle_strain_reported OR deep_scratch_reported
  -> abrasion_stress = INSPECTION_REQUIRED

ELSE IF corner_wear_reported AND material/subtype in [printed_canvas, coated_canvas, smooth_coated_cowhide, natural_leather, suede]
  -> abrasion_stress = ELEVATED

ELSE IF abrasive_contact_event OR overload_reported
  -> abrasion_stress = CAUTION

ELSE IF imu_energetic_event_count_7d >= beta operational count
  -> abrasion_stress = CAUTION

ELSE IF active_window_count_7d >= beta operational count OR motion_total_7d >= beta operational count
  -> abrasion_stress = CAUTION

ELSE
  -> abrasion_stress = LOW
```

주의: `maxShock`와 `motionCount`는 v1에서 단독 high-risk 판정 근거로 쓰지 않는다. sensor-only handling signal은 예방적 `CAUTION`까지만 올리며, 손상/점검 판단은 사용자 증상, hard trigger, 또는 추후 사용자 baseline 대비 변화와 결합한다. 현재 prototype의 `motion_active_windows_caution_7d = 24`, `motion_total_caution_7d = 50`은 검증된 손상 임계값이 아니라 MVP 회귀 테스트용 beta operational default다.

### 10.6 Continuous Usage/Rest Rules

```text
IF usage_days_30d is high AND symptoms exist
  -> usage_stress = ELEVATED

ELSE IF usage_days_30d is high AND post_use_care is missing
  -> usage_stress = CAUTION

ELSE IF usage_days_7d is high
  -> usage_stress = CAUTION

ELSE
  -> usage_stress = LOW
```

주의: 공식 근거에서 exact rest-day threshold가 없으므로 `high`는 사용자 baseline 또는 서비스 내부 percentile로만 정의한다. 공개 설명에서는 "연속 사용일이 많다"보다 "최근 사용 빈도가 높고 휴식/관리 기록이 부족하다"로 표현한다.

## 11. Overall Decision Logic

각 risk factor별 stress label을 계산한 뒤, overall output은 다음 규칙으로 결정한다.

```text
IF any hard inspection trigger
  -> inspection_need = REQUIRED
  -> care_need = HIGH

ELSE IF any stress label = HIGH
  -> inspection_need = CONDITIONAL
  -> care_need = HIGH

ELSE IF any stress label = ELEVATED
  -> inspection_need = CONDITIONAL
  -> care_need = MEDIUM_HIGH

ELSE IF two or more stress labels = CAUTION
  -> inspection_need = NONE or CONDITIONAL
  -> care_need = MEDIUM

ELSE IF one stress label = CAUTION
  -> inspection_need = NONE
  -> care_need = LOW_MEDIUM

ELSE
  -> inspection_need = NONE
  -> care_need = LOW
```

`CONDITIONAL`은 사용자에게 증상 확인 질문을 띄우는 단계다.

예:

```text
"물 얼룩, 냄새, 표면 끈적임, 경화가 보이나요?"
```

## 12. Output Contract

```json
{
  "item_id": "string",
  "material_id": "natural_leather",
  "stress_labels": {
    "humidity": "ELEVATED",
    "temperature_heat": "LOW",
    "dryness": "LOW",
    "uv_light": "UNKNOWN",
    "physical_shock_abrasion": "LOW",
    "continuous_usage_rest": "CAUTION"
  },
  "care_need": "MEDIUM_HIGH",
  "inspection_need": "CONDITIONAL",
  "matched_kb_entries": ["KB-007", "KB-010", "KB-012"],
  "triggered_rules": ["humidity_wet_event_sensitive_material", "light_direct_sun_sensitive_material"],
  "recommended_actions": [
    "blot_with_lint_free_cloth",
    "dry_at_room_temperature",
    "avoid_direct_heat",
    "avoid_direct_sunlight",
    "rotate_usage"
  ],
  "explanation_inputs": {
    "primary_reason": "Natural leather has high sensitivity to water and moisture exposure.",
    "evidence_notes": [
      "Leather high humidity candidate: >65% RH",
      "Natural leather is delicate and easily stained/scratched according to brand guidance."
    ]
  }
}
```

## 13. LLM Explanation Rules

LLM은 판단하지 않는다. LLM은 rule engine output을 사용자 언어로 바꾼다.

LLM 입력:

- material
- stress_labels
- triggered_rules
- recommended_actions
- matched evidence notes
- inspection_need

LLM 금지:

- 새로운 threshold 생성
- 손상 확률 생성
- 출처에 없는 케어 제품 추천
- "확실히 손상됨" 같은 단정

LLM 권장 표현:

```text
"현재 기록상 습기 관련 노출이 높게 평가되었습니다."
"이 소재는 물 접촉 후 얼룩이나 경화가 생길 수 있어, 직접 열을 피하고 실온에서 말리는 것이 안전합니다."
"곰팡이 냄새나 표면 끈적임이 있다면 자가 관리보다 브랜드/전문가 점검을 권장합니다."
```

## 14. Validation Case Template

```json
{
  "case_id": "VC-001",
  "material_id": "natural_leather",
  "material_subtypes": ["vachetta"],
  "features": {
    "rh_hours_gt_65_7d": 8,
    "wet_event_reported": true,
    "water_stain_reported": false,
    "visible_mould_reported": false
  },
  "expected": {
    "stress_labels": {
      "humidity": "ELEVATED"
    },
    "care_need": "MEDIUM_HIGH",
    "inspection_need": "CONDITIONAL",
    "recommended_actions_include": [
      "blot_with_lint_free_cloth",
      "dry_at_room_temperature",
      "avoid_direct_heat"
    ]
  }
}
```

## 15. Initial Validation Cases

| case_id | material | scenario | expected |
| --- | --- | --- | --- |
| `VC-001` | `natural_leather/vachetta` | wet event, no symptom | humidity `ELEVATED`, inspection `CONDITIONAL` |
| `VC-002` | `natural_leather` | visible mould | inspection `REQUIRED` |
| `VC-003` | `suede` | wet event + nap matting | inspection `REQUIRED` |
| `VC-004` | `coated_cowhide` | RH >65% sustained, no symptom | humidity `CAUTION` |
| `VC-005` | `coated_cowhide/patent_or_glossy_finish` | tacky coating | inspection `REQUIRED` |
| `VC-006` | `canvas/coated_canvas` | RH >80% stagnant + odour | inspection `REQUIRED` |
| `VC-007` | `printed_canvas` | corner wear + frequent use | abrasion `ELEVATED`, care `MEDIUM_HIGH` |
| `VC-008` | `canvas_with_leather_trim` | RH <30% + trim cracking | inspection `REQUIRED` |
| `VC-009` | `suede` | direct sun exposure + fading | light `ELEVATED`, inspection `CONDITIONAL` |
| `VC-010` | `coated_cowhide` | overload + shape collapse | inspection `CONDITIONAL` |
| `VC-011` | `coated_cowhide` | 90% RH for 48h, no symptom | humidity `HIGH`, inspection `CONDITIONAL` |

## 16. Open Questions for v1 Beta

1. RH threshold breach를 몇 시간 이상부터 `CAUTION` 또는 `ELEVATED`로 볼 것인가?
2. `repeated exposure pattern`은 7일/30일 중 어떤 window로 볼 것인가?
3. `usage_days_30d is high`를 사용자 baseline으로 볼 것인가, 서비스 전체 percentile로 볼 것인가?
4. light sensor가 없을 때 direct sunlight proxy를 어떻게 만들 것인가?
5. shock sensor event를 어떤 방식으로 baseline-normalize할 것인가?
6. 사진 기반 symptom detection을 사용자 self-report와 어떻게 병합할 것인가?
7. 소재 subtype을 사용자가 입력하게 할 것인가, 제품 DB/이미지 인식으로 추정할 것인가?

## 17. Next Implementation Tasks

1. 이 spec을 JSON rule configuration으로 변환한다.
2. feature extractor의 input/output schema를 확정한다.
3. validation case 30-50개를 작성한다.
4. deterministic rule evaluator prototype을 만든다.
5. LLM explanation prompt를 rule output 기반으로 설계한다.
6. beta 사용자 로그로 duration band와 usage baseline을 보정한다.
