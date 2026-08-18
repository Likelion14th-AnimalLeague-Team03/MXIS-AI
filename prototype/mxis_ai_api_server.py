#!/usr/bin/env python3
"""
MXIS AI MVP API server.

This lightweight server exposes the current prototype pipeline as a frontend-facing
endpoint:

POST /ai/care-summary
  SensorReading[] -> Feature Extractor -> Rule Evaluator -> aiCareSummary

It uses only the Python standard library so the MVP can be tested without a
framework setup. The Java backend can later port the same response composer.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

import mxis_feature_extractor
import mxis_openai_explanation
import mxis_rule_evaluator


API_VERSION = "mxis-ai-api-v0.1"
INTERNAL_API_KEY_HEADER = "X-MXIS-AI-Key"

LABEL_ORDER = {
    "UNKNOWN": -1,
    "LOW": 0,
    "CAUTION": 1,
    "ELEVATED": 2,
    "HIGH": 3,
    "INSPECTION_REQUIRED": 4,
}

FACTOR_MAP = {
    "humidity": "humidity",
    "temperature_heat": "temperatureHeat",
    "dryness": "dryness",
    "uv_light": "uvLight",
    "physical_shock_abrasion": "handling",
    "continuous_usage_rest": "usageRest",
}

DISPLAY_FACTOR = {
    "humidity": "humidity",
    "temperature_heat": "temperature_heat",
    "dryness": "dryness",
    "uv_light": "uv_light",
    "physical_shock_abrasion": "handling",
    "continuous_usage_rest": "usage_rest",
}

ACTION_COPY = {
    "ventilate_storage_area": {
        "title": "보관 공간 환기",
        "description": "가방을 보관하는 공간에 습기가 머무르지 않도록 가볍게 환기해주세요.",
        "category": "humidity",
    },
    "store_in_dust_bag": {
        "title": "더스트백 보관",
        "description": "먼지와 빛 노출을 줄이기 위해 통풍 가능한 상태로 더스트백에 보관해주세요.",
        "category": "storage",
    },
    "support_shape_in_storage": {
        "title": "형태 유지 보관",
        "description": "보관 중에는 내부를 가볍게 받쳐 형태가 무너지지 않게 해주세요.",
        "category": "storage",
    },
    "blot_with_lint_free_cloth": {
        "title": "부드러운 천으로 물기 제거",
        "description": "젖은 부분은 문지르지 말고 부드러운 천으로 눌러 물기를 제거해주세요.",
        "category": "humidity",
    },
    "dry_at_room_temperature": {
        "title": "실온에서 자연 건조",
        "description": "직접 열을 쓰지 말고 통풍되는 실온에서 천천히 말려주세요.",
        "category": "heat",
    },
    "avoid_direct_heat": {
        "title": "직접 열 피하기",
        "description": "드라이어, 라디에이터, 차량 내부 열로 말리지 마세요.",
        "category": "do_not_do",
    },
    "avoid_direct_sunlight": {
        "title": "직사광선 피하기",
        "description": "창가나 직사광선이 닿는 위치에 오래 두지 마세요.",
        "category": "light",
    },
    "avoid_desiccant_for_leather": {
        "title": "무분별한 제습제 피하기",
        "description": "가죽 가까이에 강한 제습제를 오래 두는 것은 피해주세요.",
        "category": "do_not_do",
    },
    "avoid_abrasive_surfaces": {
        "title": "거친 표면 피하기",
        "description": "바닥, 벽면, 거친 테이블과의 반복 마찰을 피해주세요.",
        "category": "handling",
    },
    "avoid_overpacking": {
        "title": "과적재 피하기",
        "description": "무거운 내용물을 오래 넣어두지 말고 핸들/형태 부담을 줄여주세요.",
        "category": "handling",
    },
    "rotate_usage": {
        "title": "사용 주기 분산",
        "description": "사용 빈도가 높다면 다른 제품과 번갈아 사용해 휴식 시간을 주세요.",
        "category": "usage",
    },
    "wipe_after_use_soft_dry_cloth": {
        "title": "사용 후 부드럽게 닦기",
        "description": "사용 후에는 부드러운 마른 천으로 먼지를 가볍게 정리해주세요.",
        "category": "usage",
    },
    "brush_suede_gently_when_dry": {
        "title": "스웨이드 가볍게 브러싱",
        "description": "완전히 마른 상태에서 전용 브러시로 결을 가볍게 정리해주세요.",
        "category": "suede",
    },
    "avoid_oils_perfumes_sanitizers": {
        "title": "오일/향수 접촉 피하기",
        "description": "오일, 향수, 화장품, 손소독제가 닿지 않게 주의해주세요.",
        "category": "do_not_do",
    },
    "escalate_to_brand_or_specialist": {
        "title": "전문가 점검",
        "description": "표면 증상이 확인된 경우 브랜드 또는 전문 케어 서비스를 통해 점검을 받아보세요.",
        "category": "inspection",
    },
}

DO_NOT_DO_ACTIONS = {
    "avoid_direct_heat",
    "avoid_direct_sunlight",
    "avoid_desiccant_for_leather",
    "avoid_abrasive_surfaces",
    "avoid_overpacking",
    "avoid_oils_perfumes_sanitizers",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def camel_stress_labels(stress_labels: dict[str, str]) -> dict[str, str]:
    return {
        "humidity": stress_labels.get("humidity", "UNKNOWN"),
        "temperatureHeat": stress_labels.get("temperature_heat", "UNKNOWN"),
        "dryness": stress_labels.get("dryness", "UNKNOWN"),
        "handling": stress_labels.get("physical_shock_abrasion", "UNKNOWN"),
        "usageRest": stress_labels.get("continuous_usage_rest", "UNKNOWN"),
        "uvLight": stress_labels.get("uv_light", "UNKNOWN"),
    }


def primary_factor(stress_labels: dict[str, str]) -> str | None:
    candidates = [
        (factor, label)
        for factor, label in stress_labels.items()
        if label != "UNKNOWN"
    ]
    if not candidates:
        return None
    factor, label = max(candidates, key=lambda item: LABEL_ORDER.get(item[1], -1))
    if label == "LOW":
        return None
    return DISPLAY_FACTOR.get(factor, factor)


def product_condition(stress_labels: dict[str, str], data_status: str) -> dict[str, Any]:
    if data_status != "SUFFICIENT":
        return {
            "label": "Collecting Data",
            "score": None,
            "primaryFactor": None,
            "summary": "제품 상태 분석을 위해 데이터를 수집하고 있습니다.",
        }

    score = 100
    for label in stress_labels.values():
        if label == "CAUTION":
            score -= 8
        elif label == "ELEVATED":
            score -= 18
        elif label == "HIGH":
            score -= 35
        elif label == "INSPECTION_REQUIRED":
            score -= 50
    score = max(0, min(100, score))

    if score >= 85:
        condition_label = "Excellent"
    elif score >= 60:
        condition_label = "Standard"
    else:
        condition_label = "Needs Attention"

    factor = primary_factor(stress_labels)
    summary = summary_for_factor(factor, stress_labels)
    return {
        "label": condition_label,
        "score": score,
        "primaryFactor": factor,
        "summary": summary,
    }


def summary_for_factor(factor: str | None, stress_labels: dict[str, str]) -> str:
    if any(label == "INSPECTION_REQUIRED" for label in stress_labels.values()):
        return "점검이 필요한 증상 또는 조건이 있어 전문가 확인이 권장됩니다."
    if factor == "humidity":
        return "최근 습도가 안정 범위를 벗어난 시간이 있어 보관 환경 조정이 권장됩니다."
    if factor == "temperature_heat":
        return "높은 온도 노출이 확인되어 직접 열과 고온 환경을 피하는 것이 좋습니다."
    if factor == "dryness":
        return "낮은 습도 노출이 확인되어 가죽이 건조해지지 않도록 보관 환경을 조정해주세요."
    if factor == "handling":
        return "움직임/사용 노출이 확인되어 마찰과 과적재를 줄이는 관리가 권장됩니다."
    if factor == "usage_rest":
        return "최근 사용 빈도가 높아 사용 후 관리와 형태 유지 보관이 권장됩니다."
    if factor == "uv_light":
        return "빛 노출 관련 입력이 있어 직사광선 예방 관리가 권장됩니다."
    return "현재 제공된 데이터 기준으로 보관 상태는 안정적입니다."


def action_objects(action_codes: list[str], do_not_do: bool) -> list[dict[str, Any]]:
    selected = []
    for code in action_codes:
        is_do_not = code in DO_NOT_DO_ACTIONS
        if is_do_not != do_not_do:
            continue
        copy = ACTION_COPY.get(code)
        if not copy:
            continue
        selected.append(
            {
                "code": code,
                "title": copy["title"],
                "description": copy["description"],
                "priority": len(selected) + 1,
                "category": copy["category"],
                "durationHint": None,
                "isPrimary": len(selected) == 0 and not do_not_do,
            }
        )
    return selected


def explanation(
    feature_output: dict[str, Any],
    rule_output: dict[str, Any],
    product_summary: dict[str, Any],
) -> dict[str, Any]:
    data_status = feature_output["dataSufficiency"]["status"]
    stress_labels = rule_output["stress_labels"]
    inspection_need = rule_output["inspection_need"]
    factor = product_summary.get("primaryFactor")

    if data_status != "SUFFICIENT":
        return {
            "short": "제품 상태 분석을 위해 데이터를 수집하고 있습니다.",
            "reasonBullets": [
                "최소 분석 기준을 채우려면 유효한 센서 데이터가 더 필요합니다.",
                "데이터가 충분히 쌓이면 온습도와 움직임 노출을 함께 해석합니다.",
            ],
            "sensorLimitations": [
                "현재 센서는 UV/light와 표면 증상을 직접 측정하지 않습니다."
            ],
        }

    bullets = []
    if factor == "humidity":
        rh_hours = feature_output["environmentFeatures"].get("rhHoursGt657d", 0)
        bullets.append(f"최근 분석 기간 중 고습 노출이 약 {rh_hours:g}시간 확인되었습니다.")
    elif factor == "temperature_heat":
        temp_hours = feature_output["environmentFeatures"].get("tempHoursAbove307d", 0)
        bullets.append(f"최근 분석 기간 중 높은 온도 노출이 약 {temp_hours:g}시간 확인되었습니다.")
    elif factor == "dryness":
        dry_hours = feature_output["environmentFeatures"].get("rhHoursLt307d", 0)
        bullets.append(f"최근 분석 기간 중 낮은 습도 노출이 약 {dry_hours:g}시간 확인되었습니다.")
    elif factor == "handling":
        motion_total = feature_output["handlingFeatures"].get("motionTotal7d", 0)
        bullets.append(f"최근 움직임/사용 노출 지표가 누적되었습니다. motionCount 합계는 {motion_total:g}입니다.")
    elif factor == "usage_rest":
        bullets.append("최근 사용 빈도와 관리 기록을 함께 보았을 때 예방 관리가 권장됩니다.")
    else:
        bullets.append("최근 온습도와 움직임 노출에서 강한 관리 신호는 확인되지 않았습니다.")

    if inspection_need == "REQUIRED":
        bullets.append("점검이 필요한 증상 또는 hard trigger가 보고되었습니다.")
    elif inspection_need == "CONDITIONAL":
        bullets.append("현재 센서값만으로 손상을 확정하지 않으며, 표면 증상 확인 후 점검을 고려할 수 있습니다.")
    else:
        bullets.append("현재 점검이 필요한 표면 증상은 보고되지 않았습니다.")

    limitations = []
    if stress_labels.get("uv_light") == "UNKNOWN":
        limitations.append("MVP 센서는 UV/light를 직접 측정하지 않습니다.")
    limitations.append("센서값은 노출 상태를 보여주며, 실제 표면 증상은 사용자 확인이 필요합니다.")

    return {
        "short": product_summary["summary"],
        "reasonBullets": bullets[:4],
        "sensorLimitations": limitations,
    }


def reservation_cta(rule_output: dict[str, Any]) -> dict[str, Any]:
    inspection_need = rule_output["inspection_need"]
    care_need = rule_output["care_need"]
    if inspection_need == "REQUIRED":
        return {
            "recommended": True,
            "level": "REQUIRED",
            "title": "전문가 점검을 권장합니다",
            "description": "점검이 필요한 증상 또는 조건이 있어 브랜드/전문 케어 서비스를 통한 확인이 좋습니다.",
            "suggestedServiceType": "condition_check",
            "prefillNote": "MXIS 케어 분석에서 점검 권장 신호가 확인되었습니다.",
        }
    if inspection_need == "CONDITIONAL":
        return {
            "recommended": True,
            "level": "RECOMMENDED" if care_need in {"MEDIUM_HIGH", "HIGH"} else "OPTIONAL",
            "title": "상태 확인을 고려해보세요",
            "description": "센서 노출이 누적되어 표면 증상을 확인한 뒤 필요하면 점검을 예약할 수 있습니다.",
            "suggestedServiceType": "condition_check",
            "prefillNote": "MXIS 케어 분석에서 관리 확인이 필요한 신호가 확인되었습니다.",
        }
    return {
        "recommended": False,
        "level": "NONE",
        "title": None,
        "description": None,
        "suggestedServiceType": None,
        "prefillNote": None,
    }


def feature_summary(feature_output: dict[str, Any]) -> dict[str, Any]:
    env = feature_output["environmentFeatures"]
    handling = feature_output["handlingFeatures"]
    return {
        "avgTemperature": env.get("avgTemperatureC7d"),
        "avgHumidity": env.get("avgHumidityRh7d"),
        "rhHoursGt65": env.get("rhHoursGt657d"),
        "rhHoursGt80": env.get("rhHoursGt807d"),
        "rhHoursGt90": env.get("rhHoursGt907d"),
        "rhHoursLt30": env.get("rhHoursLt307d"),
        "leatherMouldDose": env.get("leatherMouldDose7d"),
        "tempHoursAbove30": env.get("tempHoursAbove307d"),
        "warmMoistExposureHours": env.get("warmMoistExposureHours7d"),
        "motionTotal": handling.get("motionTotal7d"),
        "activeWindowCount": handling.get("activeWindowCount7d"),
        "maxShock": handling.get("maxShockG7d"),
    }


def llm_analysis_input(
    input_data: dict[str, Any],
    feature_output: dict[str, Any],
    rule_output: dict[str, Any],
    condition: dict[str, Any],
    fallback_explanation: dict[str, Any],
    fallback_reservation: dict[str, Any],
    recommended_actions: list[dict[str, Any]],
    do_not_do: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "locale": (input_data.get("llm", {}) or {}).get("locale", "ko-KR"),
        "screenContexts": (input_data.get("llm", {}) or {}).get(
            "screenContexts",
            [
                "home_summary",
                "diagnosis_home",
                "care_report",
                "environment_detail",
                "care_guide",
                "reservation_cta",
            ],
        ),
        "product": {
            "productId": input_data.get("productId"),
            "name": input_data.get("productName"),
            "materialId": input_data.get("materialId"),
            "materialSubtypes": input_data.get("materialSubtypes", []),
            "color": input_data.get("color"),
        },
        "analysis": {
            "analysisWindowDays": feature_output["analysisWindowDays"],
            "dataSufficiency": feature_output["dataSufficiency"],
            "featureSummary": feature_summary(feature_output),
            "productCondition": condition,
            "stressLabels": camel_stress_labels(rule_output["stress_labels"]),
            "careDecision": {
                "careNeed": rule_output["care_need"],
                "inspectionNeed": rule_output["inspection_need"],
                "recommendedActions": recommended_actions,
                "doNotDo": do_not_do,
            },
            "fallbackExplanation": fallback_explanation,
            "fallbackReservationCta": fallback_reservation,
            "evidence": {
                "matchedKbEntries": rule_output["matched_kb_entries"],
                "triggeredRules": rule_output["triggered_rules"],
                "sourceLevel": "A" if rule_output["matched_kb_entries"] else None,
            },
            "policy": {
                "sensorOnlyDoesNotConfirmDamage": True,
                "highMeansStrongExposureNotConfirmedDamage": True,
                "imuIsHandlingExposureProxy": True,
                "uvLightUnavailableInMvp": True,
            },
        },
    }


def deterministic_screen_copy(
    fallback_explanation: dict[str, Any],
    fallback_reservation: dict[str, Any],
    condition: dict[str, Any],
    recommended_actions: list[dict[str, Any]],
    do_not_do: list[dict[str, Any]],
) -> dict[str, Any]:
    primary = recommended_actions[0] if recommended_actions else {}
    guide = care_guide_copy(condition, fallback_explanation, primary, do_not_do)
    return {
        "homeSummary": {"short": fallback_explanation["short"]},
        "diagnosisHome": {
            "short": fallback_explanation["short"],
            "reasonBullets": fallback_explanation["reasonBullets"][:2],
        },
        "careReport": {
            "short": fallback_explanation["short"],
            "reasonBullets": fallback_explanation["reasonBullets"],
        },
        "environmentDetail": {
            "short": "그래프의 순간값보다 안정 범위를 벗어난 누적 시간이 관리 판단에 더 중요합니다.",
            "bullets": fallback_explanation["reasonBullets"],
        },
        "careGuide": {
            **guide,
            "weeklyTip": guide["tip"],
            "recommendedActionTitle": guide["title"],
            "recommendedActionDescription": guide["description"],
            "doNotDo": [item["description"] for item in do_not_do],
        },
        "reservationCta": {
            "title": fallback_reservation.get("title"),
            "description": fallback_reservation.get("description"),
            "prefillNote": fallback_reservation.get("prefillNote"),
        },
    }


def care_guide_copy(
    condition: dict[str, Any],
    fallback_explanation: dict[str, Any],
    primary_action: dict[str, Any],
    do_not_do: list[dict[str, Any]],
) -> dict[str, Any]:
    factor = condition.get("primaryFactor")
    if factor in {"humidity", "temperature_heat", "dryness", "uv_light"}:
        return {
            "careType": "ventilated_shade_storage",
            "title": "이번 주에는 직사광선을 피해 통풍이 잘되는 공간에 보관하세요",
            "description": primary_action.get("description")
            or "최근 보관 환경을 기준으로 열과 습도 변화에 주의하는 것이 좋습니다.",
            "steps": [
                "직사광선이 닿지 않는 위치로 옮겨주세요.",
                "통풍이 잘되는 공간에 자연스럽게 보관해주세요.",
                "습한 공간이나 열이 많은 공간은 피해주세요.",
            ],
            "tip": fallback_explanation["short"],
            "doNotDo": [item["description"] for item in do_not_do],
        }

    return {
        "careType": "dry_soft_cloth_wipe",
        "title": "이번 주에는 마른 부드러운 천으로 표면을 정돈해주세요",
        "description": primary_action.get("description")
        or "최근 사용 기록을 기준으로 가벼운 표면 정돈 중심의 관리가 적합합니다.",
        "steps": [
            "마른 부드러운 천을 준비해주세요.",
            "표면을 결 방향으로 가볍게 닦아주세요.",
            "강한 힘을 주지 않고 마무리해주세요.",
        ],
        "tip": fallback_explanation["short"],
        "doNotDo": [item["description"] for item in do_not_do],
    }


def maybe_generate_llm_copy(
    input_data: dict[str, Any],
    feature_output: dict[str, Any],
    rule_output: dict[str, Any],
    condition: dict[str, Any],
    fallback_explanation: dict[str, Any],
    fallback_reservation: dict[str, Any],
    recommended_actions: list[dict[str, Any]],
    do_not_do: list[dict[str, Any]],
) -> dict[str, Any]:
    fallback_screen_copy = deterministic_screen_copy(
        fallback_explanation,
        fallback_reservation,
        condition,
        recommended_actions,
        do_not_do,
    )
    if not mxis_openai_explanation.openai_enabled(input_data):
        return {
            **mxis_openai_explanation.fallback_generation("OpenAI generation is disabled."),
            "copy": {
                "explanation": fallback_explanation,
                "careCopy": {
                    "primaryActionTitle": fallback_screen_copy["careGuide"]["recommendedActionTitle"],
                    "primaryActionDescription": fallback_screen_copy["careGuide"]["recommendedActionDescription"],
                    "doNotDo": fallback_screen_copy["careGuide"]["doNotDo"],
                },
                "reservationCopy": fallback_screen_copy["reservationCta"],
                "screenCopy": fallback_screen_copy,
            },
        }

    llm_input = llm_analysis_input(
        input_data,
        feature_output,
        rule_output,
        condition,
        fallback_explanation,
        fallback_reservation,
        recommended_actions,
        do_not_do,
    )
    try:
        return mxis_openai_explanation.generate_openai_copy(llm_input)
    except Exception as exc:
        return {
            **mxis_openai_explanation.fallback_generation(str(exc)),
            "copy": {
                "explanation": fallback_explanation,
                "careCopy": {
                    "primaryActionTitle": fallback_screen_copy["careGuide"]["recommendedActionTitle"],
                    "primaryActionDescription": fallback_screen_copy["careGuide"]["recommendedActionDescription"],
                    "doNotDo": fallback_screen_copy["careGuide"]["doNotDo"],
                },
                "reservationCopy": fallback_screen_copy["reservationCta"],
                "screenCopy": fallback_screen_copy,
            },
        }


def merge_llm_copy(
    summary: dict[str, Any],
    llm_generation: dict[str, Any],
) -> None:
    copy = llm_generation["copy"]
    ai = summary["aiCareSummary"]
    ai["explanation"] = copy["explanation"]
    ai["llmCopy"] = copy["screenCopy"]

    reservation_copy = copy.get("reservationCopy", {})
    if ai["reservationCta"]["recommended"]:
        ai["reservationCta"]["title"] = reservation_copy.get("title")
        ai["reservationCta"]["description"] = reservation_copy.get("description")
        ai["reservationCta"]["prefillNote"] = reservation_copy.get("prefillNote")

    recommended = ai["careDecision"]["recommendedActions"]
    care_copy = copy.get("careCopy", {})
    if recommended and care_copy.get("primaryActionTitle"):
        recommended[0]["title"] = care_copy["primaryActionTitle"]
    if recommended and care_copy.get("primaryActionDescription"):
        recommended[0]["description"] = care_copy["primaryActionDescription"]

    ai["copyGeneration"] = {
        "source": llm_generation["source"],
        "model": llm_generation.get("model"),
        "error": llm_generation.get("error"),
        "rawResponseId": llm_generation.get("rawResponseId"),
    }


def compose_ai_care_summary(input_data: dict[str, Any]) -> dict[str, Any]:
    feature_output = mxis_feature_extractor.extract(input_data)
    rule_output = mxis_rule_evaluator.evaluate(feature_output["ruleEvaluatorInput"])
    data_sufficiency = feature_output["dataSufficiency"]
    condition = product_condition(rule_output["stress_labels"], data_sufficiency["status"])
    actions = list(rule_output["recommended_actions"])
    recommended_actions = action_objects(actions, do_not_do=False)
    do_not_do = action_objects(actions, do_not_do=True)
    fallback_explanation = explanation(feature_output, rule_output, condition)
    fallback_reservation = reservation_cta(rule_output)

    summary = {
        "schemaVersion": API_VERSION,
        "product": {
            "productId": input_data.get("productId"),
            "name": input_data.get("productName"),
            "material": input_data.get("materialId"),
            "materialSubtypes": input_data.get("materialSubtypes", []),
            "color": input_data.get("color"),
        },
        "featureSummary": feature_summary(feature_output),
        "aiCareSummary": {
            "generatedAt": now_iso(),
            "analysisWindowDays": feature_output["analysisWindowDays"],
            "dataSufficiency": {
                "status": data_sufficiency["status"],
                "reason": data_sufficiency["reason"],
                "validReadingCount": data_sufficiency["validReadingCount"],
                "coverageHours": data_sufficiency["coverageHours"],
                "lastMeasuredAt": data_sufficiency["lastMeasuredAt"],
                "lastSyncedAt": data_sufficiency["lastSyncedAt"],
            },
            "productCondition": condition,
            "stressLabels": camel_stress_labels(rule_output["stress_labels"]),
            "careDecision": {
                "careNeed": rule_output["care_need"],
                "inspectionNeed": rule_output["inspection_need"],
                "recommendedActions": recommended_actions,
                "doNotDo": do_not_do,
            },
            "explanation": fallback_explanation,
            "reservationCta": fallback_reservation,
            "evidence": {
                "matchedKbEntries": rule_output["matched_kb_entries"],
                "triggeredRules": rule_output["triggered_rules"],
                "sourceLevel": "A" if rule_output["matched_kb_entries"] else None,
            },
            "debug": {
                "featureVersion": feature_output["schemaVersion"],
                "ruleVersion": "care-model-v1.1-preventive-tier-draft",
            },
        },
    }
    llm_generation = maybe_generate_llm_copy(
        input_data,
        feature_output,
        rule_output,
        condition,
        fallback_explanation,
        fallback_reservation,
        recommended_actions,
        do_not_do,
    )
    merge_llm_copy(summary, llm_generation)
    return summary


def response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.end_headers()
    handler.wfile.write(body)


class MxisHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_OPTIONS(self) -> None:
        response(self, 204, {})

    def do_GET(self) -> None:
        path = normalized_path(self.path)
        if path == "/":
            response(
                self,
                200,
                {
                    "status": "ok",
                    "schemaVersion": API_VERSION,
                    "endpoints": {
                        "health": "GET /health",
                        "openAiStatus": "GET /ai/openai-status",
                        "demoCareSummary": "GET /ai/demo-care-summary",
                        "careSummary": "POST /ai/care-summary",
                    },
                },
            )
            return
        if path == "/health":
            response(self, 200, {"status": "ok", "schemaVersion": API_VERSION})
            return
        if path == "/ai/openai-status":
            response(self, 200, {"schemaVersion": API_VERSION, "openai": mxis_openai_explanation.openai_status()})
            return
        if path == "/ai/demo-care-summary":
            demo = mxis_feature_extractor.demo_input()
            response(self, 200, compose_ai_care_summary(demo))
            return
        response(self, 404, not_found_payload())

    def do_POST(self) -> None:
        path = normalized_path(self.path)
        if path != "/ai/care-summary":
            response(self, 404, not_found_payload())
            return
        if not internal_api_key_authorized(self.headers.get(INTERNAL_API_KEY_HEADER)):
            response(
                self,
                401,
                {
                    "error": "unauthorized",
                    "message": "Invalid internal AI API key.",
                },
            )
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(raw_body) if raw_body else {}
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object.")
            result = compose_ai_care_summary(payload)
            response(self, 200, result)
        except Exception as exc:
            response(
                self,
                400,
                {
                    "error": "bad_request",
                    "message": str(exc),
                },
            )


def normalized_path(raw_path: str) -> str:
    path = urlparse(raw_path).path
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return path


def internal_api_key_authorized(header_value: str | None) -> bool:
    expected = (os.environ.get("MXIS_AI_INTERNAL_API_KEY") or "").strip()
    if not expected:
        return True
    return (header_value or "").strip() == expected


def not_found_payload() -> dict[str, Any]:
    return {
        "error": "not_found",
        "message": "Unknown endpoint.",
        "availableEndpoints": [
            "GET /",
            "GET /health",
            "GET /ai/openai-status",
            "GET /ai/demo-care-summary",
            "POST /ai/care-summary",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MXIS AI MVP API server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), MxisHandler)
    print(f"MXIS AI API server running at http://{args.host}:{args.port}")
    print("POST /ai/care-summary")
    print("GET  /ai/demo-care-summary")
    print("GET  /health")
    server.serve_forever()


if __name__ == "__main__":
    main()
