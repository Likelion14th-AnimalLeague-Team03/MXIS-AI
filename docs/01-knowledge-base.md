# MXIS Knowledge Base v0.1

작성일: 2026-08-16

이 문서는 MXIS 럭셔리 가방 AI 케어 서비스를 위한 1차 Material x Risk Factor Knowledge Base입니다. 향후 Care-model-v1의 rule/scoring engine에 연결할 수 있도록, 실제 측정 가능한 노출값과 소재별 스트레스 해석, 그리고 케어 의사결정을 분리하는 구조로 설계했습니다.

## 핵심 Schema

각 knowledge row는 다음 필드를 가집니다.

- `material_id`: `coated_cowhide`, `natural_leather`, `suede`, `canvas`
- `risk_factor`: `humidity`, `temperature_heat`, `dryness`, `uv_light`, `physical_shock_abrasion`, `continuous_usage_rest`
- `applicability`: 해당 근거를 적용할 수 있는 제품/소재 범위
- `source_ids`: 연결된 근거 출처 ID
- `evidence_strength`: `A`, `B`, `C` 중 하나
- `threshold_candidates`: 직접 근거가 있거나 보수적으로 해석 가능한 threshold 후보만 포함
- `degradation_mechanisms`: 사용자 설명에 활용 가능한 열화 메커니즘
- `recommended_actions`: 케어 의사결정 후보
- `inspection_triggers`: 전문가/브랜드 점검으로 넘겨야 하는 조건
- `rule_engine_features`: 향후 센서값 또는 사용자 리포트로 계산할 feature 후보

## 근거 신뢰도

- `A`: 보존기관, peer-reviewed/scientific source, 또는 보존과학 threshold와 브랜드 가이드가 함께 뒷받침하는 근거
- `B`: 공식 브랜드 가이드, 또는 소재별 수치 threshold는 없지만 적용 가능한 보존 가이드
- `C`: 전문가/업계 참고 수준의 근거

v0.1에서는 어떤 row도 `C`를 1차 근거로 사용하지 않았습니다.

## Threshold 후보

현재 가장 강하게 직접 근거가 있는 threshold 후보는 다음과 같습니다.

- Leather 안정 RH 범위: Canadian Conservation Institute의 가죽 보존 가이드 기준 `45-55% RH`.
- Leather 고습 위험 후보: mould 및 hydrolytic degradation 관련 `>65% RH`.
- Leather 건조 위험 후보: moisture loss 및 embrittlement 관련 `<30% RH`.
- Leather 권장 온도: `18-20 C`.
- Leather light exposure: unpainted leather는 최대 `150 lux`; dyed/painted/light-sensitive leather는 `50 lux`; UV는 `<75 uW/lm`.
- Textile/canvas 보관 RH: Smithsonian 기준 `45% RH +/-8%`.
- Textile damp condition: `>70% RH` 회피. cotton/linen cellulosics는 stagnant air 조건에서 `80% RH` 이상일 때 mould 가능성이 커짐.
- Textile/canvas light exposure: sensitive textile guidance 기준 `50 lux`, UV `<75 uW/lm`.

현재 단계에서 수치화하지 않은 항목은 다음과 같습니다.

- shock에 대한 g-force threshold
- continuous usage/rest의 정확한 일수 threshold
- 보존 권장 온도 범위를 초과하는 "럭셔리 가방 공통 열 손상 온도" threshold

즉, 지금 단계에서는 `mould risk = 0.18` 같은 확률 예측이 아니라, `RH >65% 노출 시간이 누적되어 moisture-related degradation exposure가 HIGH` 같은 근거 기반 stress label로 표현하는 것이 맞습니다.

## 소재별 Notes

### Coated Cowhide

RH, dryness, temperature, light에 대해서는 보존과학의 leather threshold를 사용합니다. 제품 사용 맥락에서는 Hermes, Louis Vuitton, Gucci 공식 케어 가이드를 연결했습니다. 공통적으로 물, 직접적인 열/빛, 습기, 거친 표면, 과적재, 부적절한 케어 제품을 피하라는 방향입니다.

특히 anti-humidity sachet는 일반 추천으로 넣으면 안 됩니다. Hermes가 leather를 과도하게 건조시킬 수 있다고 경고하므로, MXIS는 "무조건 제습제 사용" 같은 행동을 기본 권장하면 안 됩니다.

### Natural Leather

Natural leather 또는 vegetable-tanned cowhide는 coated cowhide보다 수분과 오염에 더 민감하게 다루는 것이 안전합니다. Louis Vuitton은 natural cowhide를 섬세하고 쉽게 스크래치가 생기는 소재로 설명하고, CCI는 vegetable-tanned leather가 warm/moist 조건에서 darkening, stiffening, embrittlement, hydrolytic breakdown에 취약하다고 설명합니다.

따라서 natural leather는 물 접촉, 오일/화장품/향수/손소독제, 고습, 열, 직사광선에 대해 더 보수적인 stress label을 부여하는 쪽이 적절합니다.

### Suede

v0.1에서는 suede 전용 수치 보존 threshold를 찾지 못했기 때문에, 환경 threshold는 leather 기준을 보수적으로 적용했습니다. 다만 브랜드 가이드들은 suede를 일관되게 delicate material로 취급합니다. 비/습기, 직접 열/빛, 마찰을 피하고, 젖었을 때는 직접 열로 말리지 않고 자연 건조해야 하며, 표면 관리는 dry brush나 suede eraser 중심으로 제한하는 것이 좋습니다.

Suede의 주요 inspection trigger는 water mark, nap matting, mould, dye transfer, uneven fading입니다.

### Canvas

Canvas row는 textile conservation threshold와 luxury coated/printed canvas guidance를 함께 사용했습니다.

Plain cotton/fabric canvas는 textile의 RH/light 메커니즘이 중요합니다. 반면 coated canvas 또는 printed canvas는 Louis Vuitton이 언급한 corners, folds, bottom 부위의 abrasion/fading 가능성을 제품별 근거로 사용해야 합니다.

따라서 canvas는 단일 소재처럼 처리하지 말고, `plain_canvas`, `coated_canvas`, `printed_canvas`, `canvas_with_leather_trim` 같은 세부 flag를 rule engine feature로 두는 것이 좋습니다.

## v1 Rule Engine 권장 구조

이 KB는 deterministic evidence layer로 사용하는 것이 적절합니다.

1. `rh_hours_gt_65_7d`, `rh_hours_lt_30_7d`, `direct_sun_exposure_hours_7d`, `wet_event_reported`, `usage_days_30d` 같은 observable exposure feature를 계산합니다.
2. 계산된 exposure를 소재별 stress label로 변환합니다: `LOW`, `MODERATE`, `HIGH`, `INSPECTION_REQUIRED`.
3. 매칭된 KB row에서 care action을 생성합니다.
4. `degradation_mechanisms`와 source-backed threshold note를 사용해 사용자 설명을 생성합니다.

labelled outcome data가 쌓이기 전까지는 확률값처럼 보이는 출력은 피해야 합니다. 예를 들어 `mould risk = 0.18`보다는 `moisture-related degradation exposure: HIGH`가 현재 MXIS 단계에 더 적합합니다.

## Preventive Tier 업데이트

MXIS는 accelerated ageing 논문에서 변형이나 물성 변화가 관찰된 지점을 일상 가방의 직접 threshold로 사용하면 안 됩니다. 현재 rule layer는 다음 예방 tier로 노출을 분리합니다.

- `LOW`: 안정 범위 또는 의미 있는 노출 없음
- `CAUTION`: visible change 전에 조정해야 하는 안정 범위 이탈
- `ELEVATED`: 반복 노출, 민감 소재와 직접 이벤트의 결합, 또는 damage-supporting band에 부분 접근
- `HIGH`: CCI leather mould dose처럼 출처 기반 damage-supporting exposure band에 도달한 단계. 손상 확정은 아님
- `INSPECTION_REQUIRED`: visible symptom 또는 hard trigger

이 구조는 변형, 곰팡이, 갈라짐, 코팅 증상이 예상되기 전에 먼저 예방 알림을 주기 위한 것입니다.

## Source Register

- Canadian Conservation Institute, Care of Alum, Vegetable and Mineral-tanned Leather: https://www.canada.ca/en/conservation-institute/services/conservation-preservation-publications/canadian-conservation-institute-notes/care-alum-vegetable-mineral-leather.html
- Canadian Conservation Institute, Caring for leather, skin and fur: https://www.canada.ca/en/conservation-institute/services/preventive-conservation/guidelines-collections/caring-leather-skin-fur.html
- Canadian Conservation Institute, Light, ultraviolet and infrared: https://www.canada.ca/en/conservation-institute/services/agents-deterioration/light.html
- Canadian Conservation Institute, Caring for textiles and costumes: https://www.canada.ca/en/conservation-institute/services/preventive-conservation/guidelines-collections/textiles-costumes.html
- Canadian Conservation Institute, Textiles and the Environment: https://www.canada.ca/en/conservation-institute/services/conservation-preservation-publications/canadian-conservation-institute-notes/textiles-environment.html
- Smithsonian Museum Conservation Institute, Climate and Textiles Storage: https://mci.si.edu/climate-and-textiles-storage
- Smithsonian Museum Conservation Institute, Mold and Mildew on Textiles: https://mci.si.edu/mold-and-mildew-textiles
- Hermes, Leather Care Instructions: https://www.hermes.com/us/en/content/89726-leathercareinstructions/
- Louis Vuitton, How do I take care of my leather or canvas item?: https://en.louisvuitton.com/eng-nl/faq/products/eu-how-do-i-take-care-of-my-leather-or-canvas-item
- Louis Vuitton, Product Care: https://us.louisvuitton.com/eng-us/faq/products/welcome-to-the-house-product-care
- Gucci, Handbags Care Guide: https://www.gucci.com/us/en/nst/handbags-care-guide
- Loewe, Care Guide: https://www.loewe.com/usa/en/care-guide/CG-SLG-20.html
- Burberry, Product Care: https://us.burberry.com/c/customer-service/faqs/product-care/
