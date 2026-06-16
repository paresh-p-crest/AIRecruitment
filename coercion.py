"""Coerce heterogeneous LLM field types into expected Python shapes."""

from __future__ import annotations

import json
import re
from typing import Any


def coerce_json_value(value: Any) -> Any:
    """Parse stringified JSON; leave other values unchanged."""
    if not isinstance(value, str):
        return value

    stripped = value.strip()
    if not stripped:
        return value

    if stripped[0] in "[{":
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

    return value


def coerce_list(value: Any) -> list:
    value = coerce_json_value(value)
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    if isinstance(value, str):
        if not value.strip():
            return []
        return [line.strip() for line in re.split(r"[\n;|]", value) if line.strip()]
    return []


def coerce_str_list(value: Any) -> list[str]:
    value = coerce_json_value(value)
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        if not value.strip():
            return []
        parts = re.split(r"[\n,;|•]", value)
        return [part.strip(" -•") for part in parts if part.strip(" -•")]
    return []


def normalize_personal_info(data: Any) -> dict:
    if not isinstance(data, dict):
        data = coerce_json_value(data)
    if not isinstance(data, dict):
        return {}

    key_map = {
        "name": "Name",
        "email": "Email",
        "phone": "Phone",
        "location": "Location",
        "current_company": "Current Company",
        "current_designation": "Current Designation",
    }
    normalized: dict[str, Any] = {}
    for key, val in data.items():
        if val is None or val == "":
            continue
        alias = key_map.get(key, key)
        normalized[alias] = val
    return normalized


def normalize_skills(data: Any) -> dict:
    if hasattr(data, "model_dump"):
        data = data.model_dump(by_alias=True)
    elif not isinstance(data, dict):
        data = coerce_json_value(data)
    if not isinstance(data, dict):
        return {"Technical Skills": [], "Soft Skills": []}

    tech = data.get("Technical Skills") or data.get("technical_skills") or []
    soft = data.get("Soft Skills") or data.get("soft_skills") or []

    return {
        "Technical Skills": coerce_str_list(tech),
        "Soft Skills": coerce_str_list(soft),
    }
