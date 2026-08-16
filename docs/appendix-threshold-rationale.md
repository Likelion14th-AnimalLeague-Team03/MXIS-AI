# MXIS Rule Evaluator Threshold Rationale

작성일: 2026-08-16

이 문서는 `mxis_rule_evaluator.py`에 들어간 v1 prototype threshold의 근거와 한계를 정리한다.

## 센서 제약

현재 MXIS가 직접 제공할 수 있는 환경 정보는 다음 2개 센서뿐이다.

- 온습도 센서: temperature, relative humidity
- 6 DoF IMU: accelerometer, gyroscope

따라서 v1 evaluator는 다음을 직접 판단하지 않는다.

- UV/light exposure: 조도/UV 센서가 없으므로 사용자 보고가 있을 때만 rule 작동
- 표면 증상: 곰팡이, 얼룩, 끈적임, 갈라짐 등은 사용자 보고 또는 향후 이미지 분석 입력 필요
- 소재 subtype: 사용자가 입력하거나 제품 DB/이미지 추정으로 제공되어야 함

## RH 값

Leather 계열:

- 안정 후보: `45-55% RH`
- 고습 후보: `>65% RH`
- 건조 후보: `<30% RH`

근거:

- Canadian Conservation Institute, Care of Alum, Vegetable and Mineral-tanned Leather
- Canadian Conservation Institute, Caring for leather, skin and fur

Canvas/textile 계열:

- 보관 후보: `45% RH +/-8%`
- damp 후보: `>70% RH`
- stagnant air mould 후보: `>80% RH`

근거:

- Smithsonian Museum Conservation Institute, Climate and Textiles Storage
- Smithsonian Museum Conservation Institute, Mold and Mildew on Textiles
- Canadian Conservation Institute, Textiles and the Environment

## Duration 값

Prototype v1.1에서는 duration을 두 층으로 나눈다.

1. 공식/보존과학 자료에서 직접 제시된 time-to-growth 또는 accelerated ageing 조건
2. 제품 알림을 위한 beta default 운영 band

## Preventive tier 원칙

논문에서 관찰된 변형/물성 변화 지점은 MXIS에서 "그때부터 위험"이라는 기준이 아니다. 럭셔리 가방 케어 서비스에서는 변형이 관찰되기 전에 환경을 조정하게 만드는 것이 목적이므로, 기준을 다음처럼 나눈다.

- `LOW`: stable zone 또는 의미 있는 노출 없음
- `CAUTION`: stable zone을 벗어난 노출이 지속되어 예방 조정이 필요한 단계
- `ELEVATED`: 민감 소재와 직접 이벤트가 결합되거나 반복 노출이 누적된 단계
- `HIGH`: CCI mould dose처럼 출처 기반 damage-supporting exposure band에 도달한 단계. 손상 확정은 아님
- `INSPECTION_REQUIRED`: visible mould, water stain, cracking, tacky coating 등 증상 또는 hard trigger

따라서 accelerated ageing 논문에서 변형이 관찰된 조건은 주로 `HIGH` 또는 설명 근거의 상한선으로만 사용하고, 일상 사용자 알림은 `CAUTION`과 `ELEVATED`에서 먼저 발생하도록 설계한다.

### Leather mould dose

Leather mould 관련해서는 CCI `Removing Mould from Leather`가 다음의 시간 조건을 제시한다.

- `90-100% RH`: 대체로 2일 후 mould growth 가능
- `80% RH`: 대체로 10일 후 mould growth 가능
- `70% RH`: 대체로 100일 후 mould growth 가능

이를 evaluator에서는 다음 normalized dose로 반영했다.

```text
leather_mould_dose =
  hours_at_90_or_more / 48
+ hours_at_80_to_90 / 240
+ hours_at_70_to_80 / 2400
```

해석:

- `leather_mould_dose >= 1.0`: CCI time band상 mould-supporting exposure에 도달한 것으로 보고 humidity `HIGH`
- `leather_mould_dose >= 0.1`: 해당 band의 10% 이상에 해당하는 누적 노출로 보고 humidity `MODERATE`

이 값은 mould 발생 확률이 아니다. 온도, 오염, 통풍, 표면 상태, 기존 오염물, 사용 이력에 따라 실제 발생 여부는 달라진다.

### Beta default 운영 band

Prototype에는 여전히 다음 beta default가 있다.

- `brief_hours = 1`
- `sustained_hours = 8`
- `repeated_hours_30d = 24`

이 값들은 손상 발생 threshold가 아니다. sensor stream에서 "짧은 breach", "하루 중 의미 있는 지속 노출", "30일 반복 노출"을 구분하기 위한 운영상 band다. 특히 `RH >65%`는 CCI가 leather mould/hydrolytic degradation risk와 action plan/alarm 기준으로 제시한 값이므로, 장시간 누적 시 `MODERATE` exposure warning으로 사용한다.

보강 근거:

- CCI mould removal leather note는 mould가 대체로 `90-100% RH`에서 2일, `80% RH`에서 10일, `70% RH`에서 100일 뒤 자랄 수 있다고 설명한다.
- CCI textile note는 `70% RH`에서 mould 발달에 3개월 이상이 걸릴 수 있다고 설명한다.
- 따라서 v1의 1h/8h/24h band는 mould 발생 예측이 아니라, "노출 관리 알림"을 위한 beta default로만 사용한다.

## Leather damage 논문 근거

럭셔리 가방 완제품에 대해 "RH/온도/시간 -> 손상도"를 직접 주는 공개 논문은 제한적이다. 대신 heritage leather, vegetable-tanned leather, parchment/collagen 기반 accelerated ageing 연구가 있다.

확인한 주요 연구:

- Chen et al., `Influences of high temperature and humidity on vegetable-tanned leather`, Journal of Cultural Heritage, 2024. Vegetable-tanned leather model samples를 `80 C`와 `40-80% RH` 조건에서 `0, 2, 4, 8, 16, 32 days` 노출시켰고, faded appearance, collagen secondary structure 변화, thermal stability 감소, tensile strength 및 elongation at break 감소를 보고했다.
- `Artificial deterioration of vegetable-tanned leather under synergistic effect of temperature and humidity`, Journal of Cultural Heritage, 2021. Mimosa-tanned leather를 `80 C`, `60% RH`, `0-32 days` 조건에서 aged 처리했고 thermal stability 감소와 fiber structure destruction을 보고했다.
- Cucos et al., `DMA and DSC studies of accelerated aged parchment and vegetable-tanned leather samples`, Thermochimica Acta, 2014. Heat/moisture accelerated ageing이 denaturation temperature와 storage modulus를 낮추는 것을 보고했다.
- Badea et al. 계열 연구는 `70 C`, `30% RH`, visible light irradiation 조건에서 vegetable-tanned leather의 water dynamics, shrinkage temperature, tannin matrix 변화 등을 분석했다.

해석:

- 이 논문들은 "고온 + 습도 + 시간"이 leather의 구조적/기계적 열화를 진행시킨다는 근거로는 강하다.
- 그러나 조건이 `70-85 C` 또는 그 이상인 accelerated ageing이므로, 일상 가방 사용의 `25-40 C` 조건에 직접 duration threshold로 변환하면 과학적으로 과장이다.
- 따라서 evaluator에는 논문 조건을 일상 threshold로 직접 이식하지 않고, `temperature_extreme` 또는 `warm_moist_exposure` 설명 근거로만 사용한다.
- 실제 제품용 손상 dose 기준은 beta 센서 로그, 수리/점검 결과, 사진/증상 라벨을 통해 보정해야 한다.

## Temperature 값

Prototype에는 다음 beta default가 있다.

- `temp_warm_c = 30`
- `temp_extreme_c = 40`
- `canvas_temp_warm_c = 23.3`

근거와 해석:

- CCI leather note는 leather 보존 환경으로 `18-20 C`를 제시하고, radiator/hot display case 같은 local heat를 피하라고 한다.
- ASHRAE museum guidance는 mixed collections에서 class B의 upper temperature를 약 `86 F / 30 C`, class C의 upper limit를 약 `104 F / 40 C`로 제시한다.
- Smithsonian textile storage target은 `70 F +/-4 F`, 즉 약 `18.9-23.3 C`다.

주의:

- 이 값은 "가방 손상 온도"가 아니다.
- `30 C`는 warm exposure candidate, `40 C`는 extreme storage/event candidate로만 사용한다.
- direct heat source는 현재 센서만으로 확정할 수 없으므로 사용자 이벤트가 필요하다.

## IMU 값

Prototype에는 다음 beta default가 있다.

- `imu_energetic_accel_g = 2.0`
- `imu_high_rotation_dps = 300`
- `imu_moderate_events_7d = 5`
- `imu_high_events_7d = 15`

근거와 한계:

- wearable fall detection 논문들은 impact 또는 energetic activity detection에 대체로 약 `1.6-2.5 g` 이상의 acceleration threshold를 사용한다.
- 그러나 이 값은 인체 낙상 탐지용이지, luxury bag damage threshold가 아니다.
- 따라서 MXIS v1은 IMU를 "energetic handling exposure"로만 사용하고, 단독으로 `HIGH` 또는 `INSPECTION_REQUIRED`를 만들지 않는다.
- 실제 제품에서는 bag placement, sensor mounting, user baseline, commute pattern에 따라 calibration이 필요하다.

## 결론

v1 rule evaluator는 다음 원칙을 따른다.

1. RH/temperature는 공식 보존 가이드 기반 threshold를 preventive exposure tier로 사용한다.
2. IMU는 절대 손상 판단이 아니라 baseline 대비 handling intensity로 사용한다.
3. Light/UV는 현재 센서로 측정하지 않으므로 `UNKNOWN`을 기본값으로 둔다.
4. 증상 기반 trigger는 sensor보다 우선한다.
5. 모든 출력은 probability가 아니라 `LOW/CAUTION/ELEVATED/HIGH/INSPECTION_REQUIRED` preventive stress label이다.
