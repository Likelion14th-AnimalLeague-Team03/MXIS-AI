#!/usr/bin/env python3
"""
MXIS Care-model-v1 deterministic rule evaluator prototype.

Sensor constraint:
- Environment: temperature / relative humidity only.
- Motion: 6 DoF IMU only.
- Light/UV and visible symptoms are not inferred unless provided as user input.

This prototype intentionally avoids unsupported damage probabilities.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


STRESS_ORDER = {
    "UNKNOWN": -1,
    "LOW": 0,
    "CAUTION": 1,
    "ELEVATED": 2,
    "HIGH": 3,
    "INSPECTION_REQUIRED": 4,
}


DEFAULT_THRESHOLDS = {
    # Leather: CCI leather guidance.
    "leather_rh_high": 65.0,
    "leather_rh_low": 30.0,
    "leather_mould_rh_70": 70.0,
    "leather_mould_rh_80": 80.0,
    "leather_mould_rh_90": 90.0,
    "leather_mould_hours_at_70": 100 * 24,
    "leather_mould_hours_at_80": 10 * 24,
    "leather_mould_hours_at_90": 2 * 24,
    # Canvas/textile: CCI/Smithsonian guidance.
    "canvas_rh_damp": 70.0,
    "canvas_rh_mould_stagnant": 80.0,
    "canvas_rh_low": 37.0,
    # Temperature: ASHRAE collection categories, used only as exposure bands.
    "temp_warm_c": 30.0,
    "temp_extreme_c": 40.0,
    "canvas_temp_warm_c": 23.3,
    # Duration bands are beta defaults, not conservation damage thresholds.
    "brief_hours": 1.0,
    "sustained_hours": 8.0,
    "repeated_hours_30d": 24.0,
    # IMU energetic event candidates. These are not bag-damage thresholds.
    "imu_energetic_accel_g": 2.0,
    "imu_high_rotation_dps": 300.0,
    "imu_moderate_events_7d": 5,
    "imu_high_events_7d": 15,
    "motion_active_threshold_per_window": 1,
    "motion_active_windows_caution_7d": 24,
    "motion_total_caution_7d": 50,
    "min_sensor_readings": 24,
    "min_coverage_hours": 24,
}


MATERIAL_PARENTS = {
    "grained_coated_cowhide": "coated_cowhide",
    "smooth_coated_cowhide": "coated_cowhide",
    "patent_or_glossy_finish": "coated_cowhide",
    "vachetta": "natural_leather",
    "vegetable_tanned_cowhide": "natural_leather",
    "nubuck": "suede",
    "plain_canvas": "canvas",
    "coated_canvas": "canvas",
    "printed_canvas": "canvas",
    "canvas_with_leather_trim": "canvas",
}


SENSITIVE_TO_WATER = {
    "natural_leather",
    "vachetta",
    "vegetable_tanned_cowhide",
    "suede",
    "nubuck",
}


LEATHER_LIKE = {
    "coated_cowhide",
    "natural_leather",
    "suede",
    "grained_coated_cowhide",
    "smooth_coated_cowhide",
    "patent_or_glossy_finish",
    "vachetta",
    "vegetable_tanned_cowhide",
    "nubuck",
}


COATING_SENSITIVE = {
    "coated_cowhide",
    "patent_or_glossy_finish",
    "coated_canvas",
}


ABRASION_SENSITIVE = {
    "printed_canvas",
    "coated_canvas",
    "smooth_coated_cowhide",
    "natural_leather",
    "vachetta",
    "suede",
    "nubuck",
}


ACTION_MAP = {
    "humidity": [
        "ventilate_storage_area",
        "store_in_dust_bag",
    ],
    "wet_leather": [
        "blot_with_lint_free_cloth",
        "dry_at_room_temperature",
        "avoid_direct_heat",
    ],
    "dryness": [
        "avoid_direct_heat",
        "avoid_desiccant_for_leather",
        "support_shape_in_storage",
    ],
    "heat": [
        "avoid_direct_heat",
        "dry_at_room_temperature",
    ],
    "light": [
        "avoid_direct_sunlight",
        "store_in_dust_bag",
    ],
    "abrasion": [
        "avoid_abrasive_surfaces",
        "avoid_overpacking",
        "support_shape_in_storage",
    ],
    "usage": [
        "rotate_usage",
        "wipe_after_use_soft_dry_cloth",
        "support_shape_in_storage",
    ],
    "suede": [
        "brush_suede_gently_when_dry",
    ],
    "natural_leather": [
        "avoid_oils_perfumes_sanitizers",
    ],
    "inspection": [
        "escalate_to_brand_or_specialist",
    ],
}


@dataclass
class EvalContext:
    item_id: str
    material_id: str
    material_subtypes: list[str]
    features: dict[str, Any]
    thresholds: dict[str, float]
    triggered_rules: list[str]
    matched_kb_entries: set[str]
    actions: set[str]
    inspection_triggers: list[str]

    @property
    def material_family(self) -> str:
        return MATERIAL_PARENTS.get(self.material_id, self.material_id)

    @property
    def materials_all(self) -> set[str]:
        return {self.material_id, self.material_family, *self.material_subtypes}

    def has_material(self, *names: str) -> bool:
        return bool(self.materials_all.intersection(names))

    def add_actions(self, key: str) -> None:
        self.actions.update(ACTION_MAP.get(key, []))

    def trigger(self, code: str) -> None:
        self.triggered_rules.append(code)

    def add_kb(self, *entry_ids: str) -> None:
        self.matched_kb_entries.update(entry_ids)


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _duration_hours(reading: dict[str, Any], fallback_hours: float) -> float:
    for key in ("duration_hours", "hours"):
        if key in reading and reading[key] is not None:
            return max(float(reading[key]), 0.0)
    for key in ("duration_minutes", "minutes"):
        if key in reading and reading[key] is not None:
            return max(float(reading[key]) / 60.0, 0.0)
    return fallback_hours


def _hours_where(
    readings: list[dict[str, Any]],
    value_key: str,
    predicate,
    fallback_minutes: float,
) -> float:
    if not readings:
        return 0.0

    fallback_hours = fallback_minutes / 60.0
    total = 0.0
    sorted_readings = sorted(readings, key=lambda r: str(r.get("ts", "")))

    for idx, reading in enumerate(sorted_readings):
        value = reading.get(value_key)
        if value is None:
            continue
        try:
            matched = predicate(float(value))
        except (TypeError, ValueError):
            continue
        if not matched:
            continue

        explicit = any(k in reading for k in ("duration_hours", "hours", "duration_minutes", "minutes"))
        if explicit:
            total += _duration_hours(reading, fallback_hours)
            continue

        current_ts = _parse_ts(reading.get("ts"))
        next_ts = _parse_ts(sorted_readings[idx + 1].get("ts")) if idx + 1 < len(sorted_readings) else None
        if current_ts and next_ts and next_ts > current_ts:
            delta = (next_ts - current_ts).total_seconds() / 3600.0
            total += min(max(delta, 0.0), 6.0)
        else:
            total += fallback_hours

    return round(total, 3)


def _leather_mould_dose(readings: list[dict[str, Any]], thresholds: dict[str, float], fallback_minutes: float) -> float:
    """Estimate mould-supporting humidity dose using CCI time-to-growth bands.

    CCI leather mould guidance gives approximate growth times: 2 days at
    90-100% RH, 10 days at 80% RH, and 100 days at 70% RH. The returned
    value is a normalized exposure dose, not a probability.
    """
    if not readings:
        return 0.0

    fallback_hours = fallback_minutes / 60.0
    total = 0.0
    sorted_readings = sorted(readings, key=lambda r: str(r.get("ts", "")))

    for idx, reading in enumerate(sorted_readings):
        if "rh" not in reading:
            continue
        try:
            rh = float(reading["rh"])
        except (TypeError, ValueError):
            continue

        explicit = any(
            k in reading and reading[k] is not None
            for k in ("duration_hours", "hours", "duration_minutes", "minutes")
        )
        if explicit:
            hours = _duration_hours(reading, fallback_hours)
        else:
            current_ts = _parse_ts(reading.get("ts"))
            next_ts = _parse_ts(sorted_readings[idx + 1].get("ts")) if idx + 1 < len(sorted_readings) else None
            if current_ts and next_ts and next_ts > current_ts:
                hours = min(max((next_ts - current_ts).total_seconds() / 3600.0, 0.0), 6.0)
            else:
                hours = fallback_hours

        if rh >= thresholds["leather_mould_rh_90"]:
            total += hours / thresholds["leather_mould_hours_at_90"]
        elif rh >= thresholds["leather_mould_rh_80"]:
            total += hours / thresholds["leather_mould_hours_at_80"]
        elif rh >= thresholds["leather_mould_rh_70"]:
            total += hours / thresholds["leather_mould_hours_at_70"]

    return round(total, 4)


def _accel_magnitude_g(event: dict[str, Any]) -> float | None:
    if "accel_magnitude_g" in event:
        return float(event["accel_magnitude_g"])
    if "accel_g" in event:
        return float(event["accel_g"])
    values = []
    for key in ("ax_g", "ay_g", "az_g"):
        if key not in event:
            return None
        values.append(float(event[key]))
    return math.sqrt(sum(v * v for v in values))


def _gyro_magnitude_dps(event: dict[str, Any]) -> float | None:
    if "gyro_magnitude_dps" in event:
        return float(event["gyro_magnitude_dps"])
    values = []
    for key in ("gx_dps", "gy_dps", "gz_dps"):
        if key not in event:
            return None
        values.append(float(event[key]))
    return math.sqrt(sum(v * v for v in values))


def extract_features(input_data: dict[str, Any], thresholds: dict[str, float] | None = None) -> dict[str, Any]:
    thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    sensor_window = input_data.get("sensor_window", {})
    user_events = input_data.get("user_events", {})
    user_symptoms = input_data.get("user_symptoms", {})
    usage_log = input_data.get("usage_log", {})

    contract_readings = input_data.get("sensorReadings") or input_data.get("sensor_readings") or []
    if contract_readings and not sensor_window:
        sensor_window = {
            "sampling_interval_minutes": input_data.get("samplingIntervalMinutes", 10),
            "rh_readings": [
                {
                    "ts": r.get("measuredAt"),
                    "rh": r.get("humidity"),
                    "temp_c": r.get("temperature"),
                    "duration_minutes": input_data.get("samplingIntervalMinutes", 10),
                }
                for r in contract_readings
                if r.get("measuredAt") not in (None, 0) and r.get("humidity") is not None and r.get("temperature") is not None
            ],
            "temperature_readings": [
                {
                    "ts": r.get("measuredAt"),
                    "temp_c": r.get("temperature"),
                    "duration_minutes": input_data.get("samplingIntervalMinutes", 10),
                }
                for r in contract_readings
                if r.get("measuredAt") not in (None, 0) and r.get("temperature") is not None
            ],
            "imu_events": [
                {
                    "ts": r.get("measuredAt"),
                    "accel_magnitude_g": r.get("maxShock", 0),
                    "motionCount": r.get("motionCount", 0),
                }
                for r in contract_readings
                if r.get("measuredAt") not in (None, 0)
            ],
        }

    sampling_minutes = float(sensor_window.get("sampling_interval_minutes", input_data.get("samplingIntervalMinutes", 10)))
    rh_readings = sensor_window.get("rh_readings", [])
    temp_readings = sensor_window.get("temperature_readings", [])
    if not temp_readings:
        temp_readings = [
            {"ts": r.get("ts"), "temp_c": r.get("temp_c"), "duration_minutes": r.get("duration_minutes")}
            for r in rh_readings
            if "temp_c" in r
        ]

    stagnant_air = bool(sensor_window.get("stagnant_air", user_events.get("stagnant_air_reported", False)))

    features = {
        "sensor_reading_count": len(contract_readings) if contract_readings else len(rh_readings),
        "valid_sensor_reading_count": len(rh_readings),
        "rh_hours_gt_65_7d": _hours_where(rh_readings, "rh", lambda v: v > thresholds["leather_rh_high"], sampling_minutes),
        "rh_hours_gt_65_30d": float(input_data.get("precomputed_features", {}).get("rh_hours_gt_65_30d", 0.0)),
        "rh_hours_gt_70_7d": _hours_where(rh_readings, "rh", lambda v: v >= thresholds["canvas_rh_damp"], sampling_minutes),
        "rh_hours_gt_80_7d": _hours_where(rh_readings, "rh", lambda v: v >= thresholds["leather_mould_rh_80"], sampling_minutes),
        "rh_hours_gt_90_7d": _hours_where(rh_readings, "rh", lambda v: v >= thresholds["leather_mould_rh_90"], sampling_minutes),
        "rh_hours_gt_80_stagnant_7d": _hours_where(rh_readings, "rh", lambda v: v >= thresholds["canvas_rh_mould_stagnant"], sampling_minutes) if stagnant_air else 0.0,
        "leather_mould_dose_7d": _leather_mould_dose(rh_readings, thresholds, sampling_minutes),
        "leather_mould_dose_30d": float(input_data.get("precomputed_features", {}).get("leather_mould_dose_30d", 0.0)),
        "rh_hours_lt_30_7d": _hours_where(rh_readings, "rh", lambda v: v < thresholds["leather_rh_low"], sampling_minutes),
        "rh_hours_lt_30_30d": float(input_data.get("precomputed_features", {}).get("rh_hours_lt_30_30d", 0.0)),
        "rh_hours_lt_37_30d": float(input_data.get("precomputed_features", {}).get("rh_hours_lt_37_30d", 0.0)),
        "temp_hours_above_30_7d": _hours_where(temp_readings, "temp_c", lambda v: v > thresholds["temp_warm_c"], sampling_minutes),
        "temp_hours_above_40_7d": _hours_where(temp_readings, "temp_c", lambda v: v > thresholds["temp_extreme_c"], sampling_minutes),
        "temp_hours_above_23_3_7d": _hours_where(temp_readings, "temp_c", lambda v: v > thresholds["canvas_temp_warm_c"], sampling_minutes),
        "warm_moist_exposure_hours_7d": 0.0,
        "light_input_available": bool(user_events.get("direct_sun_exposure_reported")),
        "direct_sun_exposure_reported": bool(user_events.get("direct_sun_exposure_reported", False)),
    }

    combined = []
    for reading in rh_readings:
        if "temp_c" in reading:
            combined.append(reading)
    features["warm_moist_exposure_hours_7d"] = _hours_where(
        combined,
        "rh",
        lambda rh: rh > thresholds["leather_rh_high"],
        sampling_minutes,
    ) if combined else 0.0

    for key, value in user_events.items():
        features[key] = value
    for key, value in user_symptoms.items():
        features[key] = value
    for key, value in usage_log.items():
        features[key] = value

    imu_events = sensor_window.get("imu_events", [])
    energetic_count = 0
    rotation_count = 0
    max_accel = 0.0
    max_gyro = 0.0
    motion_total = 0
    active_window_count = 0
    for event in imu_events:
        accel = _accel_magnitude_g(event)
        gyro = _gyro_magnitude_dps(event)
        motion_count = int(event.get("motionCount", event.get("motion_count", 0)) or 0)
        motion_total += motion_count
        if motion_count >= thresholds["motion_active_threshold_per_window"]:
            active_window_count += 1
        if accel is not None:
            max_accel = max(max_accel, accel)
            if accel >= thresholds["imu_energetic_accel_g"]:
                energetic_count += 1
        if gyro is not None:
            max_gyro = max(max_gyro, gyro)
            if gyro >= thresholds["imu_high_rotation_dps"]:
                rotation_count += 1

    features["imu_energetic_event_count_7d"] = energetic_count
    features["imu_high_rotation_event_count_7d"] = rotation_count
    features["imu_max_accel_g_7d"] = round(max_accel, 3)
    features["imu_max_gyro_dps_7d"] = round(max_gyro, 3)
    features["motion_total_7d"] = motion_total
    features["active_window_count_7d"] = active_window_count
    features["inactive_window_count_7d"] = max(len(imu_events) - active_window_count, 0)
    features["data_sufficiency_status"] = data_sufficiency_status(features, rh_readings, sampling_minutes, thresholds)
    features["stagnant_air"] = stagnant_air

    return features


def data_sufficiency_status(
    features: dict[str, Any],
    rh_readings: list[dict[str, Any]],
    sampling_minutes: float,
    thresholds: dict[str, float],
) -> str:
    if features["valid_sensor_reading_count"] < thresholds["min_sensor_readings"]:
        return "INSUFFICIENT_DATA"
    if not rh_readings:
        return "INSUFFICIENT_DATA"
    timestamps = [_parse_ts(r.get("ts")) for r in rh_readings]
    timestamps = [ts for ts in timestamps if ts is not None]
    if len(timestamps) >= 2:
        coverage_hours = (max(timestamps) - min(timestamps)).total_seconds() / 3600.0
        coverage_hours += sampling_minutes / 60.0
    else:
        coverage_hours = features["valid_sensor_reading_count"] * sampling_minutes / 60.0
    if coverage_hours < thresholds["min_coverage_hours"]:
        return "INSUFFICIENT_DATA"
    return "SUFFICIENT"


def max_label(*labels: str) -> str:
    return max(labels, key=lambda label: STRESS_ORDER[label])


def hard_inspection_triggers(ctx: EvalContext) -> None:
    f = ctx.features
    m = ctx.materials_all

    if f.get("visible_mould_reported"):
        ctx.inspection_triggers.append("visible_mould")
    if f.get("musty_odour_reported") and (f.get("rh_hours_gt_65_7d", 0) > 0 or f.get("rh_hours_gt_70_7d", 0) > 0):
        ctx.inspection_triggers.append("musty_odour_after_humidity")
    if f.get("water_stain_reported") and m.intersection(SENSITIVE_TO_WATER):
        ctx.inspection_triggers.append("water_stain_natural_or_suede")
    if f.get("sticky_or_tacky_coating_reported") and m.intersection(COATING_SENSITIVE):
        ctx.inspection_triggers.append("sticky_tacky_coating")
    if f.get("blistering_reported") and m.intersection(COATING_SENSITIVE):
        ctx.inspection_triggers.append("blistering_after_moisture")
    if f.get("cracking_reported") and (m.intersection(LEATHER_LIKE) or "canvas_with_leather_trim" in m):
        ctx.inspection_triggers.append("active_cracking")
    if f.get("powdery_surface_reported") and m.intersection(LEATHER_LIKE):
        ctx.inspection_triggers.append("powdery_surface")
    if f.get("nap_matting_reported") and f.get("wet_event_reported") and m.intersection({"suede", "nubuck"}):
        ctx.inspection_triggers.append("nap_matting_after_wet")
    if f.get("handle_strain_reported"):
        ctx.inspection_triggers.append("handle_strain")

    if ctx.inspection_triggers:
        ctx.add_actions("inspection")


def evaluate_humidity(ctx: EvalContext) -> str:
    f = ctx.features
    if any(t in ctx.inspection_triggers for t in ("visible_mould", "musty_odour_after_humidity", "water_stain_natural_or_suede", "nap_matting_after_wet")):
        ctx.trigger("humidity_hard_inspection_trigger")
        ctx.add_actions("inspection")
        return "INSPECTION_REQUIRED"

    if ctx.material_family == "canvas":
        ctx.add_kb("KB-019")
        if f.get("rh_hours_gt_80_stagnant_7d", 0) >= ctx.thresholds["brief_hours"]:
            ctx.trigger("canvas_stagnant_rh_gt_80")
            ctx.add_actions("humidity")
            return "ELEVATED"
        if f.get("rh_hours_gt_70_7d", 0) >= ctx.thresholds["sustained_hours"] or f.get("wet_event_reported"):
            ctx.trigger("canvas_damp_or_wet_event")
            ctx.add_actions("humidity")
            return "CAUTION"
        return "LOW"

    ctx.add_kb("KB-001" if ctx.material_family == "coated_cowhide" else "KB-007" if ctx.material_family == "natural_leather" else "KB-013")
    if f.get("wet_event_reported") and ctx.materials_all.intersection(SENSITIVE_TO_WATER):
        ctx.trigger("wet_event_sensitive_leather")
        ctx.add_actions("wet_leather")
        if ctx.has_material("natural_leather", "vachetta"):
            ctx.add_actions("natural_leather")
        if ctx.has_material("suede", "nubuck"):
            ctx.add_actions("suede")
        return "ELEVATED"
    if f.get("wet_event_reported"):
        ctx.trigger("wet_event_coated_or_less_sensitive")
        ctx.add_actions("wet_leather")
        return "CAUTION"
    if max(f.get("leather_mould_dose_7d", 0), f.get("leather_mould_dose_30d", 0)) >= 1.0:
        ctx.trigger("leather_mould_dose_reaches_cci_time_band")
        ctx.add_actions("humidity")
        return "HIGH"
    if max(f.get("leather_mould_dose_7d", 0), f.get("leather_mould_dose_30d", 0)) >= 0.1:
        ctx.trigger("leather_mould_dose_partial_cci_time_band")
        ctx.add_actions("humidity")
        return "ELEVATED"
    if f.get("rh_hours_gt_65_7d", 0) >= ctx.thresholds["sustained_hours"]:
        ctx.trigger("leather_sustained_rh_gt_65")
        ctx.add_actions("humidity")
        return "CAUTION"
    if f.get("rh_hours_gt_65_30d", 0) >= ctx.thresholds["repeated_hours_30d"]:
        ctx.trigger("leather_repeated_rh_gt_65")
        ctx.add_actions("humidity")
        return "ELEVATED"
    return "LOW"


def evaluate_dryness(ctx: EvalContext) -> str:
    f = ctx.features
    if "active_cracking" in ctx.inspection_triggers or "powdery_surface" in ctx.inspection_triggers:
        ctx.trigger("dryness_hard_inspection_trigger")
        ctx.add_actions("inspection")
        return "INSPECTION_REQUIRED"

    if ctx.material_family == "canvas":
        ctx.add_kb("KB-021")
        if ctx.has_material("canvas_with_leather_trim") and f.get("rh_hours_lt_30_7d", 0) >= ctx.thresholds["brief_hours"]:
            ctx.trigger("canvas_trim_leather_dryness")
            ctx.add_actions("dryness")
            return "CAUTION"
        if f.get("rh_hours_lt_37_30d", 0) >= ctx.thresholds["repeated_hours_30d"]:
            ctx.trigger("canvas_low_rh_repeated")
            return "CAUTION"
        return "LOW"

    ctx.add_kb("KB-003" if ctx.material_family == "coated_cowhide" else "KB-009" if ctx.material_family == "natural_leather" else "KB-015")
    if f.get("stiffness_reported") and f.get("rh_hours_lt_30_7d", 0) >= ctx.thresholds["brief_hours"]:
        ctx.trigger("leather_stiffness_low_rh")
        ctx.add_actions("dryness")
        return "ELEVATED"
    if f.get("rh_hours_lt_30_7d", 0) >= ctx.thresholds["sustained_hours"] or f.get("rh_hours_lt_30_30d", 0) >= ctx.thresholds["repeated_hours_30d"]:
        ctx.trigger("leather_low_rh_exposure")
        ctx.add_actions("dryness")
        return "CAUTION"
    return "LOW"


def evaluate_heat(ctx: EvalContext) -> str:
    f = ctx.features
    if any(t in ctx.inspection_triggers for t in ("sticky_tacky_coating", "blistering_after_moisture", "active_cracking")) and f.get("direct_heat_event_reported"):
        ctx.trigger("heat_symptom_after_direct_heat")
        ctx.add_actions("inspection")
        return "INSPECTION_REQUIRED"

    ctx.add_kb("KB-002" if ctx.material_family == "coated_cowhide" else "KB-008" if ctx.material_family == "natural_leather" else "KB-014" if ctx.material_family == "suede" else "KB-020")
    if f.get("temp_hours_above_40_7d", 0) >= ctx.thresholds["brief_hours"]:
        ctx.trigger("temperature_extreme_above_40c")
        ctx.add_actions("heat")
        return "HIGH"
    if f.get("direct_heat_event_reported"):
        ctx.trigger("direct_heat_event")
        ctx.add_actions("heat")
        return "ELEVATED"
    if ctx.has_material("natural_leather", "vachetta", "vegetable_tanned_cowhide") and f.get("warm_moist_exposure_hours_7d", 0) >= ctx.thresholds["sustained_hours"]:
        ctx.trigger("natural_leather_warm_moist_exposure")
        ctx.add_actions("heat")
        return "ELEVATED"
    if f.get("temp_hours_above_30_7d", 0) >= ctx.thresholds["sustained_hours"]:
        ctx.trigger("temperature_warm_above_30c")
        ctx.add_actions("heat")
        return "CAUTION"
    return "LOW"


def evaluate_light(ctx: EvalContext) -> str:
    f = ctx.features
    ctx.add_kb("KB-004" if ctx.material_family == "coated_cowhide" else "KB-010" if ctx.material_family == "natural_leather" else "KB-016" if ctx.material_family == "suede" else "KB-022")

    if not f.get("light_input_available"):
        ctx.trigger("light_not_measured_by_available_sensors")
        return "UNKNOWN"
    if f.get("fading_or_yellowing_reported") and f.get("direct_sun_exposure_reported"):
        ctx.trigger("fading_after_direct_sun")
        ctx.add_actions("light")
        return "ELEVATED"
    if f.get("direct_sun_exposure_reported"):
        ctx.trigger("direct_sun_reported")
        ctx.add_actions("light")
        return "CAUTION"
    return "LOW"


def evaluate_abrasion(ctx: EvalContext) -> str:
    f = ctx.features
    if "handle_strain" in ctx.inspection_triggers or f.get("deep_scratch_reported"):
        ctx.trigger("abrasion_hard_inspection_trigger")
        ctx.add_actions("inspection")
        return "INSPECTION_REQUIRED"

    ctx.add_kb("KB-005" if ctx.material_family == "coated_cowhide" else "KB-011" if ctx.material_family == "natural_leather" else "KB-017" if ctx.material_family == "suede" else "KB-023")
    if f.get("corner_wear_reported") and ctx.materials_all.intersection(ABRASION_SENSITIVE):
        ctx.trigger("corner_wear_sensitive_material")
        ctx.add_actions("abrasion")
        return "ELEVATED"
    if f.get("abrasive_contact_event") or f.get("overload_reported"):
        ctx.trigger("reported_abrasive_or_overload_event")
        ctx.add_actions("abrasion")
        return "CAUTION"
    if f.get("imu_energetic_event_count_7d", 0) >= ctx.thresholds["imu_high_events_7d"]:
        ctx.trigger("imu_high_energetic_handling_count")
        ctx.add_actions("abrasion")
        return "CAUTION"
    if f.get("imu_energetic_event_count_7d", 0) >= ctx.thresholds["imu_moderate_events_7d"]:
        ctx.trigger("imu_moderate_energetic_handling_count")
        return "CAUTION"
    if (
        f.get("active_window_count_7d", 0) >= ctx.thresholds["motion_active_windows_caution_7d"]
        or f.get("motion_total_7d", 0) >= ctx.thresholds["motion_total_caution_7d"]
    ):
        ctx.trigger("motion_count_handling_exposure")
        ctx.add_actions("usage")
        return "CAUTION"
    return "LOW"


def evaluate_usage(ctx: EvalContext) -> str:
    f = ctx.features
    ctx.add_kb("KB-006" if ctx.material_family == "coated_cowhide" else "KB-012" if ctx.material_family == "natural_leather" else "KB-018" if ctx.material_family == "suede" else "KB-024")
    symptoms = any(
        bool(f.get(k))
        for k in (
            "corner_wear_reported",
            "shape_collapse_reported",
            "handle_strain_reported",
            "nap_matting_reported",
            "water_stain_reported",
        )
    )
    usage_30d = int(f.get("usage_days_30d", 0) or 0)
    usage_7d = int(f.get("usage_days_7d", 0) or 0)

    # These are beta defaults because official sources recommend rotation/rest
    # without exact day counts.
    high_30d = usage_30d >= 24
    high_7d = usage_7d >= 6

    if high_30d and symptoms:
        ctx.trigger("high_usage_with_symptoms")
        ctx.add_actions("usage")
        return "ELEVATED"
    if high_30d and not f.get("post_use_wipe_confirmed") and not ctx.has_material("suede", "nubuck"):
        ctx.trigger("high_usage_missing_post_use_wipe")
        ctx.add_actions("usage")
        return "CAUTION"
    if high_7d:
        ctx.trigger("high_usage_7d_beta_default")
        ctx.add_actions("usage")
        return "CAUTION"
    return "LOW"


def overall_decision(stress_labels: dict[str, str], ctx: EvalContext) -> dict[str, str]:
    hard_trigger = bool(ctx.inspection_triggers)
    conditional_trigger = bool(ctx.features.get("shape_collapse_reported") or ctx.features.get("dye_transfer_reported"))
    high_count = sum(1 for label in stress_labels.values() if label == "HIGH")
    elevated_count = sum(1 for label in stress_labels.values() if label == "ELEVATED")
    caution_count = sum(1 for label in stress_labels.values() if label == "CAUTION")

    if hard_trigger or any(label == "INSPECTION_REQUIRED" for label in stress_labels.values()):
        return {"care_need": "HIGH", "inspection_need": "REQUIRED"}
    if high_count:
        return {"care_need": "HIGH", "inspection_need": "CONDITIONAL"}
    if elevated_count:
        return {"care_need": "MEDIUM_HIGH", "inspection_need": "CONDITIONAL"}
    if conditional_trigger:
        return {"care_need": "MEDIUM", "inspection_need": "CONDITIONAL"}
    if caution_count >= 2:
        return {"care_need": "MEDIUM", "inspection_need": "CONDITIONAL"}
    if caution_count == 1:
        return {"care_need": "LOW_MEDIUM", "inspection_need": "NONE"}
    return {"care_need": "LOW", "inspection_need": "NONE"}


def evaluate(input_data: dict[str, Any], thresholds: dict[str, float] | None = None) -> dict[str, Any]:
    thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or input_data.get("threshold_overrides", {}))}
    material_id = input_data.get("material_id", "unknown")
    material_subtypes = input_data.get("material_subtypes", [])
    features = {**extract_features(input_data, thresholds), **input_data.get("precomputed_features", {})}

    ctx = EvalContext(
        item_id=input_data.get("item_id", "unknown"),
        material_id=material_id,
        material_subtypes=material_subtypes,
        features=features,
        thresholds=thresholds,
        triggered_rules=[],
        matched_kb_entries=set(),
        actions=set(),
        inspection_triggers=[],
    )

    hard_inspection_triggers(ctx)

    stress_labels = {
        "humidity": evaluate_humidity(ctx),
        "temperature_heat": evaluate_heat(ctx),
        "dryness": evaluate_dryness(ctx),
        "uv_light": evaluate_light(ctx),
        "physical_shock_abrasion": evaluate_abrasion(ctx),
        "continuous_usage_rest": evaluate_usage(ctx),
    }

    decision = overall_decision(stress_labels, ctx)
    if decision["inspection_need"] == "REQUIRED":
        ctx.add_actions("inspection")

    return {
        "item_id": ctx.item_id,
        "material_id": material_id,
        "material_family": ctx.material_family,
        "material_subtypes": material_subtypes,
        "stress_labels": stress_labels,
        **decision,
        "matched_kb_entries": sorted(ctx.matched_kb_entries),
        "triggered_rules": ctx.triggered_rules,
        "inspection_triggers": ctx.inspection_triggers,
        "recommended_actions": sorted(ctx.actions),
        "computed_features": features,
        "sensor_limitations": [
            "No direct UV/light measurement is available from temperature/RH + 6 DoF IMU sensors.",
            "IMU events are treated as energetic handling exposure, not as bag damage thresholds.",
            "Visible symptoms require user report or future image analysis."
        ],
        "explanation_inputs": {
            "primary_reason": summarize_primary_reason(stress_labels, ctx),
            "evidence_notes": evidence_notes(ctx),
        },
    }


def summarize_primary_reason(stress_labels: dict[str, str], ctx: EvalContext) -> str:
    if ctx.inspection_triggers:
        return "A hard inspection trigger was reported, so expert or brand inspection is prioritized."
    ranked = sorted(stress_labels.items(), key=lambda item: STRESS_ORDER[item[1]], reverse=True)
    factor, label = ranked[0]
    if label == "UNKNOWN":
        return "Available sensors do not provide enough information for this factor."
    if label == "LOW":
        return "No meaningful exposure or symptom was detected in the provided inputs."
    return f"{factor} is the primary exposure driver with stress label {label}."


def evidence_notes(ctx: EvalContext) -> list[str]:
    notes = []
    if ctx.material_family in {"coated_cowhide", "natural_leather", "suede"}:
        notes.append("Leather RH candidates: stable 45-55% RH, high humidity >65% RH, dryness <30% RH.")
        notes.append("Leather mould dose uses CCI bands: 90-100% RH for 2 days, 80% RH for 10 days, 70% RH for 100 days.")
    if ctx.material_family == "canvas":
        notes.append("Canvas/textile RH candidates: target around 45% RH +/-8%, damp >70% RH, stagnant mould support above 80% RH.")
    notes.append("Temperature bands are exposure stress candidates, not universal luxury-bag damage thresholds.")
    notes.append("IMU thresholds are configurable energetic-event candidates and must be calibrated to bag placement and user baseline.")
    return notes


def run_validation(path: Path) -> dict[str, Any]:
    cases = json.loads(path.read_text(encoding="utf-8"))
    results = []
    passed = 0
    for case in cases:
        output = evaluate(case["input"])
        expected = case["expected"]
        ok = True
        for key, expected_value in expected.get("stress_labels", {}).items():
            ok = ok and output["stress_labels"].get(key) == expected_value
        for key in ("care_need", "inspection_need"):
            if key in expected:
                ok = ok and output.get(key) == expected[key]
        for action in expected.get("recommended_actions_include", []):
            ok = ok and action in output["recommended_actions"]
        passed += int(ok)
        results.append({
            "case_id": case["case_id"],
            "passed": ok,
            "expected": expected,
            "actual": {
                "stress_labels": output["stress_labels"],
                "care_need": output["care_need"],
                "inspection_need": output["inspection_need"],
                "recommended_actions": output["recommended_actions"],
                "triggered_rules": output["triggered_rules"],
            },
        })
    return {"passed": passed, "total": len(cases), "results": results}


def demo_input() -> dict[str, Any]:
    return {
        "item_id": "demo-natural-leather-001",
        "material_id": "natural_leather",
        "material_subtypes": ["vachetta"],
        "sensor_window": {
            "sampling_interval_minutes": 60,
            "rh_readings": [
                {"ts": "2026-08-15T09:00:00", "rh": 68, "temp_c": 29},
                {"ts": "2026-08-15T10:00:00", "rh": 70, "temp_c": 30},
                {"ts": "2026-08-15T11:00:00", "rh": 66, "temp_c": 31}
            ],
            "temperature_readings": [
                {"ts": "2026-08-15T09:00:00", "temp_c": 29},
                {"ts": "2026-08-15T10:00:00", "temp_c": 30},
                {"ts": "2026-08-15T11:00:00", "temp_c": 31}
            ],
            "imu_events": [
                {"ts": "2026-08-15T10:05:00", "accel_magnitude_g": 2.2, "gyro_magnitude_dps": 180}
            ]
        },
        "user_events": {
            "wet_event_reported": True,
            "direct_heat_event_reported": False,
            "direct_sun_exposure_reported": False,
            "abrasive_contact_event": False,
            "overload_reported": False
        },
        "user_symptoms": {
            "visible_mould_reported": False,
            "musty_odour_reported": False,
            "water_stain_reported": False
        },
        "usage_log": {
            "usage_days_7d": 5,
            "usage_days_30d": 18,
            "rest_days_30d": 12
        }
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate MXIS Care-model-v1 rules.")
    parser.add_argument("input", nargs="?", help="Path to input JSON.")
    parser.add_argument("--demo", action="store_true", help="Run built-in demo input.")
    parser.add_argument("--validate", help="Path to validation cases JSON.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    if args.validate:
        result = run_validation(Path(args.validate))
    elif args.demo:
        result = evaluate(demo_input())
    elif args.input:
        result = evaluate(json.loads(Path(args.input).read_text(encoding="utf-8")))
    else:
        parser.error("Provide an input JSON, --demo, or --validate.")

    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))


if __name__ == "__main__":
    main()
