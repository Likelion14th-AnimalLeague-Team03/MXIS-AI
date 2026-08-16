#!/usr/bin/env python3
"""
MXIS weak supervision synthetic dataset generator.

Generates SensorReading-level synthetic cases, runs them through:
- mxis_feature_extractor.py
- mxis_rule_evaluator.py

and stores weak labels plus actual rule outputs.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


BASE_TIME = 1_735_123_456
WINDOW_SECONDS = 600


@dataclass(frozen=True)
class Scenario:
    name: str
    material_id: str
    material_subtypes: list[str]
    builder: Callable[[], dict[str, Any]]
    weak_labels: dict[str, Any]
    label_sources: list[str]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def reading(
    idx: int,
    *,
    temp: float = 24.0,
    rh: float = 52.0,
    shock: float = 0.12,
    motion: int = 0,
    measured_at: int | None = None,
) -> dict[str, Any]:
    return {
        "sequence": idx + 1,
        "measuredAt": BASE_TIME + idx * WINDOW_SECONDS if measured_at is None else measured_at,
        "temperature": round(temp, 2),
        "humidity": round(rh, 2),
        "maxShock": round(shock, 3),
        "motionCount": motion,
    }


def series(
    count: int,
    *,
    temp: float = 24.0,
    rh: float = 52.0,
    shock: float = 0.12,
    motion: int = 0,
    start_idx: int = 0,
) -> list[dict[str, Any]]:
    return [
        reading(start_idx + idx, temp=temp, rh=rh, shock=shock, motion=motion)
        for idx in range(count)
    ]


def base_case(
    scenario: str,
    material_id: str,
    material_subtypes: list[str],
    sensor_readings: list[dict[str, Any]],
    *,
    user_events: dict[str, Any] | None = None,
    user_symptoms: dict[str, Any] | None = None,
    analysis_window_days: int = 7,
) -> dict[str, Any]:
    return {
        "scenario": scenario,
        "productId": f"SYN-{scenario}",
        "deviceId": f"DEV-{scenario}",
        "materialId": material_id,
        "materialSubtypes": material_subtypes,
        "analysisWindowDays": analysis_window_days,
        "samplingWindowSeconds": WINDOW_SECONDS,
        "sensorReadings": sensor_readings,
        "userEvents": user_events or {},
        "userSymptoms": user_symptoms or {},
    }


def stable_storage() -> dict[str, Any]:
    return base_case(
        "stable_storage",
        "coated_cowhide",
        ["grained_coated_cowhide"],
        series(144, temp=22.0, rh=52.0, shock=0.08, motion=0),
    )


def sustained_high_humidity() -> dict[str, Any]:
    return base_case(
        "sustained_high_humidity",
        "coated_cowhide",
        ["grained_coated_cowhide"],
        [*series(48, temp=24.0, rh=52.0), *series(48, temp=25.0, rh=68.0, start_idx=48), *series(48, temp=24.0, rh=52.0, start_idx=96)],
    )


def mould_dose_approach() -> dict[str, Any]:
    # 80% RH for 24h => 24 / 240 = 0.1 dose.
    return base_case(
        "mould_dose_approach",
        "coated_cowhide",
        ["grained_coated_cowhide"],
        series(144, temp=24.0, rh=82.0, shock=0.08, motion=0),
    )


def mould_dose_reached() -> dict[str, Any]:
    # 90% RH for 48h => 48 / 48 = 1.0 dose.
    return base_case(
        "mould_dose_reached",
        "coated_cowhide",
        ["grained_coated_cowhide"],
        series(288, temp=24.0, rh=91.0, shock=0.08, motion=0),
    )


def dry_leather_exposure() -> dict[str, Any]:
    return base_case(
        "dry_leather_exposure",
        "natural_leather",
        ["vachetta"],
        [*series(48, temp=22.0, rh=52.0), *series(96, temp=23.0, rh=25.0, start_idx=48)],
    )


def warm_moist_sensitive_leather() -> dict[str, Any]:
    return base_case(
        "warm_moist_sensitive_leather",
        "natural_leather",
        ["vachetta"],
        [*series(48, temp=24.0, rh=52.0), *series(96, temp=32.0, rh=68.0, start_idx=48)],
    )


def active_handling_day() -> dict[str, Any]:
    readings = []
    for idx in range(144):
        active = idx % 3 == 0
        readings.append(reading(idx, temp=24.0, rh=52.0, shock=0.35 if active else 0.08, motion=4 if active else 0))
    return base_case("active_handling_day", "canvas", ["printed_canvas"], readings)


def shock_heavy_windows() -> dict[str, Any]:
    readings = []
    for idx in range(144):
        shock = 2.4 if idx in {20, 40, 80, 100, 120} else 0.12
        motion = 6 if shock > 2 else 0
        readings.append(reading(idx, temp=24.0, rh=52.0, shock=shock, motion=motion))
    return base_case("shock_heavy_windows", "coated_cowhide", ["smooth_coated_cowhide"], readings)


def insufficient_data() -> dict[str, Any]:
    return base_case("insufficient_data", "coated_cowhide", [], series(8, temp=24.0, rh=52.0))


def timestamp_missing() -> dict[str, Any]:
    readings = [reading(0, measured_at=0), *series(24, temp=24.0, rh=52.0, start_idx=1)]
    return base_case("timestamp_missing", "canvas", ["coated_canvas"], readings)


def wet_event_sensitive_material() -> dict[str, Any]:
    return base_case(
        "wet_event_sensitive_material",
        "natural_leather",
        ["vachetta"],
        series(144, temp=24.0, rh=52.0),
        user_events={"wetEventReported": True},
    )


def visible_mould_reported() -> dict[str, Any]:
    return base_case(
        "visible_mould_reported",
        "coated_cowhide",
        [],
        series(144, temp=24.0, rh=68.0),
        user_symptoms={"visibleMouldReported": True},
    )


def suede_wet_nap_matting() -> dict[str, Any]:
    return base_case(
        "suede_wet_nap_matting",
        "suede",
        ["nubuck"],
        series(144, temp=24.0, rh=52.0),
        user_events={"wetEventReported": True},
        user_symptoms={"napMattingReported": True},
    )


def coated_finish_tacky() -> dict[str, Any]:
    return base_case(
        "coated_finish_tacky",
        "coated_cowhide",
        ["patent_or_glossy_finish"],
        series(144, temp=24.0, rh=52.0),
        user_symptoms={"stickyOrTackyCoatingReported": True},
    )


SCENARIOS: list[Scenario] = [
    Scenario("stable_storage", "coated_cowhide", ["grained_coated_cowhide"], stable_storage, {"stressLabels": {"humidity": "LOW"}, "careNeed": "LOW", "inspectionNeed": "NONE"}, ["LF_stable_storage", "KB-001"]),
    Scenario("sustained_high_humidity", "coated_cowhide", ["grained_coated_cowhide"], sustained_high_humidity, {"stressLabels": {"humidity": "CAUTION"}, "careNeed": "LOW_MEDIUM", "inspectionNeed": "NONE"}, ["LF_leather_rh65_sustained", "KB-001"]),
    Scenario("mould_dose_approach", "coated_cowhide", ["grained_coated_cowhide"], mould_dose_approach, {"stressLabels": {"humidity": "ELEVATED"}, "careNeed": "MEDIUM_HIGH", "inspectionNeed": "CONDITIONAL"}, ["LF_leather_mould_dose_partial", "CCI_LEATHER_MOULD", "KB-001"]),
    Scenario("mould_dose_reached", "coated_cowhide", ["grained_coated_cowhide"], mould_dose_reached, {"stressLabels": {"humidity": "HIGH"}, "careNeed": "HIGH", "inspectionNeed": "CONDITIONAL"}, ["LF_leather_mould_dose_full", "CCI_LEATHER_MOULD", "KB-001"]),
    Scenario("dry_leather_exposure", "natural_leather", ["vachetta"], dry_leather_exposure, {"stressLabels": {"dryness": "CAUTION"}, "careNeed": "LOW_MEDIUM", "inspectionNeed": "NONE"}, ["LF_low_rh_leather", "KB-009"]),
    Scenario("warm_moist_sensitive_leather", "natural_leather", ["vachetta"], warm_moist_sensitive_leather, {"stressLabels": {"temperature_heat": "ELEVATED"}, "careNeed": "MEDIUM_HIGH", "inspectionNeed": "CONDITIONAL"}, ["LF_warm_moist_sensitive_leather", "KB-008"]),
    Scenario("active_handling_day", "canvas", ["printed_canvas"], active_handling_day, {"stressLabels": {"physical_shock_abrasion": "CAUTION"}, "careNeed": "LOW_MEDIUM", "inspectionNeed": "NONE"}, ["LF_imu_handling_high", "KB-023"]),
    Scenario("shock_heavy_windows", "coated_cowhide", ["smooth_coated_cowhide"], shock_heavy_windows, {"stressLabels": {"physical_shock_abrasion": "CAUTION"}, "careNeed": "LOW_MEDIUM", "inspectionNeed": "NONE"}, ["LF_imu_shock_windows", "KB-005"]),
    Scenario("insufficient_data", "coated_cowhide", [], insufficient_data, {"dataSufficiency": "INSUFFICIENT_DATA"}, ["LF_insufficient_data"]),
    Scenario("timestamp_missing", "canvas", ["coated_canvas"], timestamp_missing, {"dataQuality": {"invalidTimestampCount": 1}}, ["LF_timestamp_missing"]),
    Scenario("wet_event_sensitive_material", "natural_leather", ["vachetta"], wet_event_sensitive_material, {"stressLabels": {"humidity": "ELEVATED"}, "careNeed": "MEDIUM_HIGH", "inspectionNeed": "CONDITIONAL"}, ["LF_sensitive_material_wet_event", "KB-007"]),
    Scenario("visible_mould_reported", "coated_cowhide", [], visible_mould_reported, {"stressLabels": {"humidity": "INSPECTION_REQUIRED"}, "careNeed": "HIGH", "inspectionNeed": "REQUIRED"}, ["LF_visible_mould", "KB-001"]),
    Scenario("suede_wet_nap_matting", "suede", ["nubuck"], suede_wet_nap_matting, {"stressLabels": {"humidity": "INSPECTION_REQUIRED"}, "careNeed": "HIGH", "inspectionNeed": "REQUIRED"}, ["LF_suede_wet_nap_matting", "KB-013"]),
    Scenario("coated_finish_tacky", "coated_cowhide", ["patent_or_glossy_finish"], coated_finish_tacky, {"inspectionNeed": "REQUIRED"}, ["LF_coated_finish_tacky", "KB-001"]),
]


def primary_mismatches(expected: dict[str, Any], rule_output: dict[str, Any], feature_output: dict[str, Any]) -> list[dict[str, Any]]:
    mismatches = []
    for factor, expected_label in expected.get("stressLabels", {}).items():
        actual = rule_output.get("stress_labels", {}).get(factor)
        if actual != expected_label:
            mismatches.append({"field": f"stressLabels.{factor}", "expected": expected_label, "actual": actual})
    if "careNeed" in expected and rule_output.get("care_need") != expected["careNeed"]:
        mismatches.append({"field": "careNeed", "expected": expected["careNeed"], "actual": rule_output.get("care_need")})
    if "inspectionNeed" in expected and rule_output.get("inspection_need") != expected["inspectionNeed"]:
        mismatches.append({"field": "inspectionNeed", "expected": expected["inspectionNeed"], "actual": rule_output.get("inspection_need")})
    if "dataSufficiency" in expected and feature_output.get("dataSufficiency", {}).get("status") != expected["dataSufficiency"]:
        mismatches.append({"field": "dataSufficiency", "expected": expected["dataSufficiency"], "actual": feature_output.get("dataSufficiency", {}).get("status")})
    invalid_expected = expected.get("dataQuality", {}).get("invalidTimestampCount")
    if invalid_expected is not None and feature_output.get("dataSufficiency", {}).get("invalidTimestampCount") != invalid_expected:
        mismatches.append({"field": "invalidTimestampCount", "expected": invalid_expected, "actual": feature_output.get("dataSufficiency", {}).get("invalidTimestampCount")})
    return mismatches


def compact_feature_output(feature_output: dict[str, Any]) -> dict[str, Any]:
    env = feature_output.get("environmentFeatures", {})
    handling = feature_output.get("handlingFeatures", {})
    return {
        "dataSufficiency": feature_output.get("dataSufficiency"),
        "environmentFeatures": {
            "rhHoursGt657d": env.get("rhHoursGt657d"),
            "rhHoursGt807d": env.get("rhHoursGt807d"),
            "rhHoursGt907d": env.get("rhHoursGt907d"),
            "rhHoursLt307d": env.get("rhHoursLt307d"),
            "leatherMouldDose7d": env.get("leatherMouldDose7d"),
            "tempHoursAbove307d": env.get("tempHoursAbove307d"),
            "warmMoistExposureHours7d": env.get("warmMoistExposureHours7d"),
        },
        "handlingFeatures": {
            "motionTotal7d": handling.get("motionTotal7d"),
            "activeWindowCount7d": handling.get("activeWindowCount7d"),
            "maxShockG7d": handling.get("maxShockG7d"),
            "shockWindowsGt2g7d": handling.get("shockWindowsGt2g7d"),
        },
    }


def generate_dataset(limit: int | None = None) -> dict[str, Any]:
    root = Path(__file__).resolve().parent
    feature_extractor = load_module("mxis_feature_extractor", root / "mxis_feature_extractor.py")
    rule_evaluator = load_module("mxis_rule_evaluator", root / "mxis_rule_evaluator.py")

    selected = SCENARIOS[:limit] if limit else SCENARIOS
    cases = []
    passed = 0

    for index, scenario in enumerate(selected, 1):
        input_case = scenario.builder()
        feature_output = feature_extractor.extract(input_case)
        rule_output = rule_evaluator.evaluate(feature_output["ruleEvaluatorInput"])
        mismatches = primary_mismatches(scenario.weak_labels, rule_output, feature_output)
        passed += int(not mismatches)
        cases.append(
            {
                "caseId": f"SYN-{index:04d}",
                "scenario": scenario.name,
                "materialId": input_case["materialId"],
                "materialSubtypes": input_case.get("materialSubtypes", []),
                "samplingWindowSeconds": input_case["samplingWindowSeconds"],
                "analysisWindowDays": input_case["analysisWindowDays"],
                "sensorReadings": input_case["sensorReadings"],
                "userEvents": input_case.get("userEvents", {}),
                "userSymptoms": input_case.get("userSymptoms", {}),
                "featureOutput": compact_feature_output(feature_output),
                "ruleOutput": {
                    "stressLabels": rule_output["stress_labels"],
                    "careNeed": rule_output["care_need"],
                    "inspectionNeed": rule_output["inspection_need"],
                    "recommendedActions": rule_output["recommended_actions"],
                    "triggeredRules": rule_output["triggered_rules"],
                },
                "weakLabels": scenario.weak_labels,
                "labelSources": scenario.label_sources,
                "validation": {
                    "passed": not mismatches,
                    "mismatches": mismatches,
                },
            }
        )

    return {
        "schemaVersion": "mxis-weak-supervision-synthetic-dataset-v0.1",
        "caseCount": len(cases),
        "validation": {"passed": passed, "total": len(cases)},
        "cases": cases,
    }


def summary(dataset: dict[str, Any]) -> dict[str, Any]:
    by_scenario = {}
    by_inspection = {}
    for case in dataset["cases"]:
        by_scenario[case["scenario"]] = by_scenario.get(case["scenario"], 0) + 1
        inspection = case["ruleOutput"]["inspectionNeed"]
        by_inspection[inspection] = by_inspection.get(inspection, 0) + 1
    return {
        "schemaVersion": dataset["schemaVersion"],
        "caseCount": dataset["caseCount"],
        "validation": dataset["validation"],
        "byScenario": by_scenario,
        "byInspectionNeed": by_inspection,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate MXIS synthetic weak supervision dataset.")
    parser.add_argument("--out", default="outputs/mxis_synthetic_dataset_sample.json", help="Output dataset JSON path.")
    parser.add_argument("--summary-out", default="outputs/mxis_synthetic_dataset_summary.json", help="Output summary JSON path.")
    parser.add_argument("--limit", type=int, default=None, help="Limit scenario count.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print files.")
    args = parser.parse_args()

    dataset = generate_dataset(args.limit)
    indent = 2 if args.pretty else None
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(dataset, ensure_ascii=False, indent=indent), encoding="utf-8")

    summary_path = Path(args.summary_out)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary(dataset), ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary(dataset), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
