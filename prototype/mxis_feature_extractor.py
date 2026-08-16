#!/usr/bin/env python3
"""
MXIS Feature Extractor MVP prototype.

Input:
- Smart Charm SensorReading DTOs from the MVP sensor contract.

Output:
- Data sufficiency block.
- Environment and handling features.
- Rule Evaluator adapter input.

The extractor does not judge product condition or damage.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULTS = {
    "sampling_window_seconds": 600,
    "min_valid_readings": 24,
    "min_coverage_hours": 24.0,
    "stale_after_hours": 24.0,
    "active_day_min_windows": 3,
}


THRESHOLDS = {
    "leather_rh_high": 65.0,
    "leather_rh_low": 30.0,
    "canvas_rh_damp": 70.0,
    "canvas_rh_low": 37.0,
    "leather_mould_rh_70": 70.0,
    "leather_mould_rh_80": 80.0,
    "leather_mould_rh_90": 90.0,
    "leather_mould_hours_at_70": 100 * 24.0,
    "leather_mould_hours_at_80": 10 * 24.0,
    "leather_mould_hours_at_90": 2 * 24.0,
    "temp_warm_c": 30.0,
    "temp_extreme_c": 40.0,
    "canvas_temp_upper_c": 23.3,
    "shock_gt_1g": 1.0,
    "shock_gt_2g": 2.0,
}


@dataclass(frozen=True)
class CleanReading:
    sequence: int | None
    measured_at: int
    temperature: float
    humidity: float
    max_shock: float
    motion_count: int


def iso_from_epoch(seconds: int | float | None) -> str | None:
    if seconds in (None, 0):
        return None
    return datetime.fromtimestamp(float(seconds), tz=timezone.utc).isoformat().replace("+00:00", "Z")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def dedupe_readings(readings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Dedupe by sequence when available, preferring valid timestamps."""
    by_sequence: dict[int, dict[str, Any]] = {}
    without_sequence: list[dict[str, Any]] = []

    for reading in readings:
        sequence = as_int(reading.get("sequence"))
        if sequence is None:
            without_sequence.append(reading)
            continue

        previous = by_sequence.get(sequence)
        if previous is None:
            by_sequence[sequence] = reading
            continue

        current_valid_time = bool(as_int(reading.get("measuredAt")) or as_int(reading.get("measured_at")))
        previous_valid_time = bool(as_int(previous.get("measuredAt")) or as_int(previous.get("measured_at")))
        if current_valid_time and not previous_valid_time:
            by_sequence[sequence] = reading

    return [*without_sequence, *by_sequence.values()]


def clean_readings(readings: list[dict[str, Any]]) -> tuple[list[CleanReading], dict[str, int]]:
    invalid_timestamp = 0
    invalid_environment = 0
    invalid_imu = 0
    cleaned: list[CleanReading] = []

    for reading in dedupe_readings(readings):
        measured_at = as_int(reading.get("measuredAt", reading.get("measured_at")))
        temperature = as_float(reading.get("temperature"))
        humidity = as_float(reading.get("humidity"))

        if not measured_at:
            invalid_timestamp += 1
            continue
        if temperature is None or humidity is None:
            invalid_environment += 1
            continue

        max_shock = as_float(reading.get("maxShock", reading.get("max_shock")))
        motion_count = as_int(reading.get("motionCount", reading.get("motion_count")))
        if max_shock is None or motion_count is None:
            invalid_imu += 1

        cleaned.append(
            CleanReading(
                sequence=as_int(reading.get("sequence")),
                measured_at=measured_at,
                temperature=temperature,
                humidity=humidity,
                max_shock=max_shock or 0.0,
                motion_count=motion_count or 0,
            )
        )

    cleaned.sort(key=lambda item: (item.measured_at, item.sequence if item.sequence is not None else -1))
    return cleaned, {
        "invalidTimestampCount": invalid_timestamp,
        "invalidEnvironmentCount": invalid_environment,
        "invalidImuCount": invalid_imu,
    }


def filter_analysis_window(
    readings: list[CleanReading],
    analysis_window_days: int,
    analysis_end_at: int | None,
) -> tuple[list[CleanReading], int | None]:
    if not readings:
        return [], analysis_end_at
    end_at = analysis_end_at or max(r.measured_at for r in readings)
    start_at = end_at - analysis_window_days * 24 * 3600
    return [r for r in readings if start_at < r.measured_at <= end_at], end_at


def coverage_hours(readings: list[CleanReading], sampling_window_seconds: int) -> float:
    if not readings:
        return 0.0
    if len(readings) == 1:
        return round(sampling_window_seconds / 3600.0, 3)
    span = max(r.measured_at for r in readings) - min(r.measured_at for r in readings)
    return round((span + sampling_window_seconds) / 3600.0, 3)


def count_hours(readings: list[CleanReading], sampling_window_seconds: int, predicate) -> float:
    hours_per_reading = sampling_window_seconds / 3600.0
    return round(sum(1 for reading in readings if predicate(reading)) * hours_per_reading, 3)


def average(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 3)


def rounded_max(values: list[float]) -> float | None:
    return round(max(values), 3) if values else None


def rounded_min(values: list[float]) -> float | None:
    return round(min(values), 3) if values else None


def leather_mould_dose(readings: list[CleanReading], sampling_window_seconds: int) -> float:
    hours_per_reading = sampling_window_seconds / 3600.0
    total = 0.0
    for reading in readings:
        rh = reading.humidity
        if rh >= THRESHOLDS["leather_mould_rh_90"]:
            total += hours_per_reading / THRESHOLDS["leather_mould_hours_at_90"]
        elif rh >= THRESHOLDS["leather_mould_rh_80"]:
            total += hours_per_reading / THRESHOLDS["leather_mould_hours_at_80"]
        elif rh >= THRESHOLDS["leather_mould_rh_70"]:
            total += hours_per_reading / THRESHOLDS["leather_mould_hours_at_70"]
    return round(total, 4)


def day_key(epoch_seconds: int) -> str:
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).date().isoformat()


def active_day_stats(readings: list[CleanReading], active_day_min_windows: int) -> dict[str, int]:
    if not readings:
        return {
            "activeDays": 0,
            "inactiveDays": 0,
            "consecutiveActiveDays": 0,
            "consecutiveInactiveDays": 0,
        }

    by_day: dict[str, int] = {}
    for reading in readings:
        by_day.setdefault(day_key(reading.measured_at), 0)
        if reading.motion_count >= 1:
            by_day[day_key(reading.measured_at)] += 1

    days = sorted(by_day)
    active_flags = [by_day[day] >= active_day_min_windows for day in days]
    active_days = sum(1 for flag in active_flags if flag)
    inactive_days = len(active_flags) - active_days

    consecutive_active = 0
    for flag in reversed(active_flags):
        if not flag:
            break
        consecutive_active += 1

    consecutive_inactive = 0
    for flag in reversed(active_flags):
        if flag:
            break
        consecutive_inactive += 1

    return {
        "activeDays": active_days,
        "inactiveDays": inactive_days,
        "consecutiveActiveDays": consecutive_active,
        "consecutiveInactiveDays": consecutive_inactive,
    }


def data_sufficiency(
    readings: list[CleanReading],
    counts: dict[str, int],
    sampling_window_seconds: int,
    last_synced_at: int | None,
    analysis_end_at: int | None,
) -> dict[str, Any]:
    valid_count = len(readings)
    coverage = coverage_hours(readings, sampling_window_seconds)
    last_measured_at = max((r.measured_at for r in readings), default=None)

    status = "SUFFICIENT"
    reason = None

    if valid_count == 0:
        status = "NO_DATA"
        reason = "NO_VALID_READING"
    elif valid_count < DEFAULTS["min_valid_readings"]:
        status = "INSUFFICIENT_DATA"
        reason = "MIN_READING_COUNT_NOT_MET"
    elif coverage < DEFAULTS["min_coverage_hours"]:
        status = "INSUFFICIENT_DATA"
        reason = "MIN_COVERAGE_HOURS_NOT_MET"

    reference_time = analysis_end_at or last_synced_at or last_measured_at
    if status == "SUFFICIENT" and last_measured_at and reference_time:
        stale_hours = (reference_time - last_measured_at) / 3600.0
        if stale_hours > DEFAULTS["stale_after_hours"]:
            status = "STALE_DATA"
            reason = "STALE_LAST_SYNC"

    return {
        "status": status,
        "reason": reason,
        "validReadingCount": valid_count,
        "requiredReadingCount": DEFAULTS["min_valid_readings"],
        "coverageHours": coverage,
        "requiredCoverageHours": DEFAULTS["min_coverage_hours"],
        "invalidTimestampCount": counts["invalidTimestampCount"],
        "invalidEnvironmentCount": counts["invalidEnvironmentCount"],
        "invalidImuCount": counts["invalidImuCount"],
        "lastMeasuredAt": iso_from_epoch(last_measured_at),
        "lastSyncedAt": iso_from_epoch(last_synced_at),
    }


def environment_features(readings: list[CleanReading], sampling_window_seconds: int, suffix: str) -> dict[str, Any]:
    temperatures = [reading.temperature for reading in readings]
    humidities = [reading.humidity for reading in readings]
    features = {
        f"avgTemperatureC{suffix}": average(temperatures),
        f"maxTemperatureC{suffix}": rounded_max(temperatures),
        f"minTemperatureC{suffix}": rounded_min(temperatures),
        f"avgHumidityRh{suffix}": average(humidities),
        f"maxHumidityRh{suffix}": rounded_max(humidities),
        f"minHumidityRh{suffix}": rounded_min(humidities),
        f"rhHoursGt65{suffix}": count_hours(readings, sampling_window_seconds, lambda r: r.humidity > THRESHOLDS["leather_rh_high"]),
        f"rhHoursGt70{suffix}": count_hours(readings, sampling_window_seconds, lambda r: r.humidity >= THRESHOLDS["leather_mould_rh_70"]),
        f"rhHoursGt80{suffix}": count_hours(readings, sampling_window_seconds, lambda r: r.humidity >= THRESHOLDS["leather_mould_rh_80"]),
        f"rhHoursGt90{suffix}": count_hours(readings, sampling_window_seconds, lambda r: r.humidity >= THRESHOLDS["leather_mould_rh_90"]),
        f"rhHoursLt30{suffix}": count_hours(readings, sampling_window_seconds, lambda r: r.humidity < THRESHOLDS["leather_rh_low"]),
        f"rhHoursLt37{suffix}": count_hours(readings, sampling_window_seconds, lambda r: r.humidity < THRESHOLDS["canvas_rh_low"]),
        f"leatherMouldDose{suffix}": leather_mould_dose(readings, sampling_window_seconds),
        f"tempHoursAbove30{suffix}": count_hours(readings, sampling_window_seconds, lambda r: r.temperature > THRESHOLDS["temp_warm_c"]),
        f"tempHoursAbove40{suffix}": count_hours(readings, sampling_window_seconds, lambda r: r.temperature > THRESHOLDS["temp_extreme_c"]),
        f"tempHoursAbove233{suffix}": count_hours(readings, sampling_window_seconds, lambda r: r.temperature > THRESHOLDS["canvas_temp_upper_c"]),
        f"warmMoistExposureHours{suffix}": count_hours(
            readings,
            sampling_window_seconds,
            lambda r: r.humidity > THRESHOLDS["leather_rh_high"] and r.temperature > THRESHOLDS["temp_warm_c"],
        ),
    }
    return features


def handling_features(readings: list[CleanReading], suffix: str, active_day_min_windows: int) -> dict[str, Any]:
    valid_windows = len(readings)
    active_window_count = sum(1 for reading in readings if reading.motion_count >= 1)
    inactive_window_count = max(valid_windows - active_window_count, 0)
    motion_total = sum(reading.motion_count for reading in readings)
    max_shocks = [reading.max_shock for reading in readings]
    day_stats = active_day_stats(readings, active_day_min_windows)

    return {
        f"motionTotal{suffix}": motion_total,
        f"motionAvgPerActiveWindow{suffix}": round(motion_total / active_window_count, 3) if active_window_count else 0.0,
        f"activeWindowCount{suffix}": active_window_count,
        f"inactiveWindowCount{suffix}": inactive_window_count,
        f"activeWindowRatio{suffix}": round(active_window_count / valid_windows, 3) if valid_windows else 0.0,
        f"maxShockG{suffix}": rounded_max(max_shocks) or 0.0,
        f"avgMaxShockG{suffix}": average(max_shocks) or 0.0,
        f"shockWindowsGt1g{suffix}": sum(1 for reading in readings if reading.max_shock >= THRESHOLDS["shock_gt_1g"]),
        f"shockWindowsGt2g{suffix}": sum(1 for reading in readings if reading.max_shock >= THRESHOLDS["shock_gt_2g"]),
        f"activeDays{suffix}": day_stats["activeDays"],
        f"inactiveDays{suffix}": day_stats["inactiveDays"],
        "consecutiveActiveDays": day_stats["consecutiveActiveDays"],
        "consecutiveInactiveDays": day_stats["consecutiveInactiveDays"],
    }


def snake_rule_input(
    product_id: str | None,
    device_id: str | None,
    material_id: str | None,
    material_subtypes: list[str],
    analysis_window_days: int,
    sampling_window_seconds: int,
    readings: list[CleanReading],
    user_events: dict[str, Any],
    user_symptoms: dict[str, Any],
    usage_log: dict[str, Any],
) -> dict[str, Any]:
    sampling_minutes = sampling_window_seconds / 60.0
    return {
        "item_id": product_id or device_id or "unknown",
        "material_id": material_id or "unknown",
        "material_subtypes": material_subtypes,
        "analysisWindowDays": analysis_window_days,
        "samplingIntervalMinutes": sampling_minutes,
        "sensorReadings": [
            {
                "sequence": reading.sequence,
                "measuredAt": reading.measured_at,
                "temperature": reading.temperature,
                "humidity": reading.humidity,
                "maxShock": reading.max_shock,
                "motionCount": reading.motion_count,
            }
            for reading in readings
        ],
        "user_events": camel_to_snake_dict(user_events),
        "user_symptoms": camel_to_snake_dict(user_symptoms),
        "usage_log": camel_to_snake_dict(usage_log),
    }


def camel_to_snake(name: str) -> str:
    out = []
    for char in name:
        if char.isupper():
            out.append("_")
            out.append(char.lower())
        else:
            out.append(char)
    return "".join(out).lstrip("_")


def camel_to_snake_dict(values: dict[str, Any]) -> dict[str, Any]:
    return {camel_to_snake(key): value for key, value in values.items()}


def suffix_for_days(days: int) -> str:
    return f"{days}d" if days not in (365, 366) else "1y"


def extract(input_data: dict[str, Any]) -> dict[str, Any]:
    raw_readings = input_data.get("sensorReadings") or input_data.get("sensor_readings") or []
    analysis_window_days = int(input_data.get("analysisWindowDays", input_data.get("analysis_window_days", 7)) or 7)
    sampling_window_seconds = int(input_data.get("samplingWindowSeconds", input_data.get("sampling_window_seconds", DEFAULTS["sampling_window_seconds"])) or DEFAULTS["sampling_window_seconds"])
    analysis_end_at = as_int(input_data.get("analysisEndAt", input_data.get("analysis_end_at")))
    last_synced_at = as_int(input_data.get("lastSyncedAt", input_data.get("last_synced_at")))
    product_id = input_data.get("productId", input_data.get("product_id"))
    device_id = input_data.get("deviceId", input_data.get("device_id"))
    material_id = input_data.get("materialId", input_data.get("material_id"))
    material_subtypes = input_data.get("materialSubtypes", input_data.get("material_subtypes", [])) or []
    user_events = input_data.get("userEvents", input_data.get("user_events", {})) or {}
    user_symptoms = input_data.get("userSymptoms", input_data.get("user_symptoms", {})) or {}
    usage_log = input_data.get("usageLog", input_data.get("usage_log", {})) or {}

    cleaned, invalid_counts = clean_readings(raw_readings)
    windowed, resolved_end_at = filter_analysis_window(cleaned, analysis_window_days, analysis_end_at)
    suffix = suffix_for_days(analysis_window_days)
    active_day_min_windows = int(input_data.get("activeDayMinWindows", DEFAULTS["active_day_min_windows"]) or DEFAULTS["active_day_min_windows"])

    env = environment_features(windowed, sampling_window_seconds, suffix)
    handling = handling_features(windowed, suffix, active_day_min_windows)
    sufficiency = data_sufficiency(windowed, invalid_counts, sampling_window_seconds, last_synced_at, resolved_end_at)

    quality_flags = {
        "hasEnoughCoverage": sufficiency["coverageHours"] >= DEFAULTS["min_coverage_hours"],
        "hasEnoughReadings": sufficiency["validReadingCount"] >= DEFAULTS["min_valid_readings"],
        "hasRecentSync": sufficiency["status"] != "STALE_DATA",
        "hasTimestampGaps": has_timestamp_gaps(windowed, sampling_window_seconds),
        "hasInvalidTimestamps": sufficiency["invalidTimestampCount"] > 0,
        "imuFailureUnknown": True,
        "lightUnavailable": True,
    }

    return {
        "schemaVersion": "mxis-feature-extractor-v0.1",
        "productId": product_id,
        "deviceId": device_id,
        "materialId": material_id,
        "materialSubtypes": material_subtypes,
        "analysisWindowDays": analysis_window_days,
        "samplingWindowSeconds": sampling_window_seconds,
        "generatedAt": now_iso(),
        "analysisEndAt": iso_from_epoch(resolved_end_at),
        "dataSufficiency": sufficiency,
        "environmentFeatures": env,
        "handlingFeatures": handling,
        "qualityFlags": quality_flags,
        "userEvents": user_events,
        "userSymptoms": user_symptoms,
        "ruleEvaluatorInput": snake_rule_input(
            product_id,
            device_id,
            material_id,
            material_subtypes,
            analysis_window_days,
            sampling_window_seconds,
            windowed,
            user_events,
            user_symptoms,
            usage_log,
        ),
    }


def has_timestamp_gaps(readings: list[CleanReading], sampling_window_seconds: int) -> bool:
    if len(readings) < 2:
        return False
    max_allowed_gap = sampling_window_seconds * 2
    for previous, current in zip(readings, readings[1:]):
        if current.measured_at - previous.measured_at > max_allowed_gap:
            return True
    return False


def demo_input() -> dict[str, Any]:
    base = 1_735_123_456
    readings = []
    for idx in range(144):
        readings.append(
            {
                "sequence": idx + 1,
                "measuredAt": base + idx * 600,
                "temperature": 24.8,
                "humidity": 68.4 if idx < 60 else 52.0,
                "maxShock": 0.32,
                "motionCount": 2 if idx % 4 == 0 else 0,
            }
        )
    return {
        "productId": "MCM001",
        "deviceId": "SC001",
        "materialId": "coated_cowhide",
        "materialSubtypes": ["grained_coated_cowhide"],
        "analysisWindowDays": 7,
        "samplingWindowSeconds": 600,
        "sensorReadings": readings,
        "userEvents": {},
        "userSymptoms": {},
    }


def value_at_path(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def run_validation(path: Path) -> dict[str, Any]:
    cases = json.loads(path.read_text(encoding="utf-8"))
    results = []
    passed = 0
    for case in cases:
        output = extract(case["input"])
        ok = True
        mismatches = []
        for path_expr, expected in case.get("expected", {}).items():
            actual = value_at_path(output, path_expr)
            if actual != expected:
                ok = False
                mismatches.append({"path": path_expr, "expected": expected, "actual": actual})
        passed += int(ok)
        results.append({"caseId": case["caseId"], "passed": ok, "mismatches": mismatches})
    return {"passed": passed, "total": len(cases), "results": results}


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract MXIS sensor features.")
    parser.add_argument("input", nargs="?", help="Path to Feature Extractor input JSON.")
    parser.add_argument("--demo", action="store_true", help="Run built-in demo input.")
    parser.add_argument("--validate", help="Path to validation cases JSON.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    if args.validate:
        result = run_validation(Path(args.validate))
    elif args.demo:
        result = extract(demo_input())
    elif args.input:
        result = extract(json.loads(Path(args.input).read_text(encoding="utf-8")))
    else:
        parser.error("Provide input JSON, --demo, or --validate.")

    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))


if __name__ == "__main__":
    main()
