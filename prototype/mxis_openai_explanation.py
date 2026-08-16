#!/usr/bin/env python3
"""
OpenAI-backed explanation generation for MXIS AI Care Model.

The LLM is copy-generation only. It must not change rule labels, care decisions,
inspection decisions, thresholds, or evidence.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5-mini")
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

FORBIDDEN_CLAIMS = [
    "손상되었습니다",
    "곰팡이가 생겼습니다",
    "갈라졌습니다",
    "확률",
    "수리비",
    "보증",
    "정품",
    "가품",
    "2g 이상이면 손상",
]

SYSTEM_PROMPT = """You are MXIS Care Explanation Writer.

Your job is to convert structured material-care analysis into concise Korean user-facing copy.
You must not create new risk judgments, probabilities, thresholds, diagnoses, repair estimates, or inspection requirements.
Use only the provided structured input.

The product is a luxury bag. Write calmly, precisely, and preventively.
Do not overstate damage. Sensor-only exposure means exposure, not confirmed damage.

Return valid JSON only."""

DEVELOPER_PROMPT = """Follow these rules:

1. Output language must be Korean unless input.locale says otherwise.
2. Use polite but concise Korean.
3. Do not mention AI unless the product UI explicitly needs it.
4. Never output damage probability, mould probability, cracking probability, repair cost, warranty advice, or brand-authenticity advice.
5. If dataSufficiency.status is not SUFFICIENT, focus on data collection status and avoid care conclusions.
6. If uvLight is UNKNOWN because light is not measured, say that UV/light is not directly measured by the current sensor.
7. If handling is based on IMU, explain it as movement/usage exposure rather than shock damage.
8. If inspectionNeed is REQUIRED, recommend brand or specialist inspection without guaranteeing damage.
9. If inspectionNeed is CONDITIONAL, ask the user to check visible symptoms and offer inspection as an option.
10. Generate copy for each frontend screen context in screenCopy.
11. Keep the output within the schema. Do not add extra fields."""


LLM_OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["explanation", "careCopy", "reservationCopy", "screenCopy"],
    "properties": {
        "explanation": {
            "type": "object",
            "additionalProperties": False,
            "required": ["short", "reasonBullets", "sensorLimitations"],
            "properties": {
                "short": {"type": "string"},
                "reasonBullets": {"type": "array", "items": {"type": "string"}},
                "sensorLimitations": {"type": "array", "items": {"type": "string"}},
            },
        },
        "careCopy": {
            "type": "object",
            "additionalProperties": False,
            "required": ["primaryActionTitle", "primaryActionDescription", "doNotDo"],
            "properties": {
                "primaryActionTitle": {"type": ["string", "null"]},
                "primaryActionDescription": {"type": ["string", "null"]},
                "doNotDo": {"type": "array", "items": {"type": "string"}},
            },
        },
        "reservationCopy": {
            "type": "object",
            "additionalProperties": False,
            "required": ["title", "description", "prefillNote"],
            "properties": {
                "title": {"type": ["string", "null"]},
                "description": {"type": ["string", "null"]},
                "prefillNote": {"type": ["string", "null"]},
            },
        },
        "screenCopy": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "homeSummary",
                "diagnosisHome",
                "careReport",
                "environmentDetail",
                "careGuide",
                "reservationCta",
            ],
            "properties": {
                "homeSummary": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["short"],
                    "properties": {"short": {"type": "string"}},
                },
                "diagnosisHome": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["short", "reasonBullets"],
                    "properties": {
                        "short": {"type": "string"},
                        "reasonBullets": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "careReport": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["short", "reasonBullets"],
                    "properties": {
                        "short": {"type": "string"},
                        "reasonBullets": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "environmentDetail": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["short", "bullets"],
                    "properties": {
                        "short": {"type": "string"},
                        "bullets": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "careGuide": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["weeklyTip", "recommendedActionTitle", "recommendedActionDescription", "doNotDo"],
                    "properties": {
                        "weeklyTip": {"type": "string"},
                        "recommendedActionTitle": {"type": ["string", "null"]},
                        "recommendedActionDescription": {"type": ["string", "null"]},
                        "doNotDo": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "reservationCta": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["title", "description", "prefillNote"],
                    "properties": {
                        "title": {"type": ["string", "null"]},
                        "description": {"type": ["string", "null"]},
                        "prefillNote": {"type": ["string", "null"]},
                    },
                },
            },
        },
    },
}


def openai_enabled(input_data: dict[str, Any]) -> bool:
    llm_options = input_data.get("llm", {}) or {}
    if llm_options.get("enabled") is True:
        return True
    return os.environ.get("MXIS_USE_OPENAI", "").lower() in {"1", "true", "yes", "on"}


def generate_openai_copy(input_data: dict[str, Any], timeout_seconds: float = 12.0) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    model = (input_data.get("llm", {}) or {}).get("model") or DEFAULT_MODEL
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": SYSTEM_PROMPT}],
            },
            {
                "role": "developer",
                "content": [{"type": "input_text", "text": DEVELOPER_PROMPT}],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "Create MXIS explanation JSON for this structured analysis.\n\n"
                        + json.dumps(input_data, ensure_ascii=False, separators=(",", ":")),
                    }
                ],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "mxis_care_explanation",
                "strict": True,
                "schema": LLM_OUTPUT_SCHEMA,
            }
        },
    }

    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API error {exc.code}: {detail[:500]}") from exc

    output_text = extract_output_text(body)
    generated = json.loads(output_text)
    validate_generated_copy(generated, input_data)
    return {
        "source": "openai",
        "model": model,
        "rawResponseId": body.get("id"),
        "copy": generated,
    }


def extract_output_text(response_body: dict[str, Any]) -> str:
    if response_body.get("output_text"):
        return str(response_body["output_text"])

    parts = []
    for item in response_body.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                parts.append(content["text"])
    if parts:
        return "".join(parts)
    raise RuntimeError("OpenAI response did not contain output_text.")


def validate_generated_copy(generated: dict[str, Any], input_data: dict[str, Any]) -> None:
    rendered = json.dumps(generated, ensure_ascii=False)
    forbidden = [claim for claim in FORBIDDEN_CLAIMS if claim in rendered]
    if forbidden:
        raise RuntimeError(f"LLM output contains forbidden claims: {', '.join(forbidden)}")

    analysis = input_data.get("analysis", {})
    stress_labels = analysis.get("stressLabels", {})
    if stress_labels.get("uvLight") == "UNKNOWN":
        limitations = generated["explanation"].get("sensorLimitations", [])
        if not any("UV" in item or "light" in item or "빛" in item for item in limitations):
            raise RuntimeError("LLM output must mention UV/light limitation when uvLight is UNKNOWN.")

    inspection_need = analysis.get("careDecision", {}).get("inspectionNeed")
    reservation = generated.get("reservationCopy", {})
    if inspection_need == "NONE" and any(reservation.get(key) for key in ("title", "description", "prefillNote")):
        raise RuntimeError("reservationCopy must be null when inspectionNeed is NONE.")


def fallback_generation(reason: str | None = None) -> dict[str, Any]:
    return {
        "source": "deterministic_fallback",
        "model": None,
        "error": reason,
    }

