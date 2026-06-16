"""Normalize and parse LLM resume extraction output across providers."""

from __future__ import annotations

import json
import re
from typing import Any

from coercion import (
    coerce_json_value,
    coerce_list,
    coerce_str_list,
    normalize_personal_info,
    normalize_skills,
)
from schemas import ExtractedResume

PERSONAL_INFO_KEYS = {"Personal_Info", "personal_info", "PersonalInfo"}
EXPERIENCE_KEYS = {
    "Professional_Experience",
    "professional_experience",
    "Experience",
    "experience",
}
EDUCATION_KEYS = {"Education", "education"}
SKILLS_KEYS = {"Skills", "skills"}


def clean_resume_text(text: str) -> str:
    """Normalize raw PDF/DOCX text for more reliable LLM extraction."""
    cleaned = text.replace("\x00", " ")
    # Word .doc hyperlinks: HYPERLINK "mailto:user@x.com"user@x.com
    cleaned = re.sub(
        r'HYPERLINK\s+"mailto:([^"]+)"\s*',
        r"\1 ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"HYPERLINK\s+\"[^\"]+\"\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"mailto:", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"-\s*page\s+\d+\s*$", "", cleaned, flags=re.MULTILINE | re.IGNORECASE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n[•●▪◦]\s*", "\n- ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


def _normalize_experience_entry(entry: Any) -> dict | None:
    if not isinstance(entry, dict):
        return None

    key_map = {
        "company_name": "Company Name",
        "job_title": "Job Title",
        "employment_type": "Employment Type",
        "start_date": "Start Date",
        "end_date": "End Date",
        "responsibilities": "Responsibilities",
        "technologies_used": "Technologies Used",
    }

    normalized: dict[str, Any] = {}
    for key, val in entry.items():
        alias = key_map.get(key, key)
        if alias in ("Responsibilities", "Technologies Used"):
            normalized[alias] = coerce_str_list(val)
        else:
            normalized[alias] = val if val not in ("", None) else None

    if not any(
        normalized.get(k)
        for k in ("Company Name", "Job Title", "Start Date", "End Date")
    ):
        return None
    return normalized


def _normalize_education_entry(entry: Any) -> dict | None:
    if not isinstance(entry, dict):
        return None

    key_map = {
        "degree": "Degree",
        "specialisation": "Specialisation",
        "specialization": "Specialisation",
        "college": "College",
        "university": "College",
        "institution": "College",
        "start_year": "Start Year",
        "end_year": "End Year",
        "grade_cgpa": "Grade/CGPA",
        "grade": "Grade/CGPA",
        "cgpa": "Grade/CGPA",
    }

    normalized: dict[str, Any] = {}
    for key, val in entry.items():
        alias = key_map.get(key, key)
        normalized[alias] = val if val not in ("", None) else None

    if not any(normalized.get(k) for k in ("Degree", "College")):
        return None
    return normalized


def _pick_section(payload: dict, keys: set[str]) -> Any:
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return None


def normalize_llm_payload(payload: Any) -> dict:
    """Coerce heterogeneous LLM output into the ExtractedResume alias dict shape."""
    if isinstance(payload, ExtractedResume):
        return payload.model_dump(by_alias=True)

    if isinstance(payload, str):
        payload = coerce_json_value(payload)
    if not isinstance(payload, dict):
        raise ValueError("LLM output is not a JSON object")

    if len(payload) == 1:
        only_val = next(iter(payload.values()))
        if isinstance(only_val, str) and only_val.strip().startswith("{"):
            payload = coerce_json_value(only_val)

    personal_raw = _pick_section(payload, PERSONAL_INFO_KEYS) or {}
    experience_raw = _pick_section(payload, EXPERIENCE_KEYS)
    education_raw = _pick_section(payload, EDUCATION_KEYS)
    skills_raw = _pick_section(payload, SKILLS_KEYS)

    experience_list = [
        item
        for item in (_normalize_experience_entry(e) for e in coerce_list(experience_raw))
        if item
    ]
    education_list = [
        item
        for item in (_normalize_education_entry(e) for e in coerce_list(education_raw))
        if item
    ]

    return {
        "Personal_Info": normalize_personal_info(personal_raw),
        "Professional_Experience": experience_list,
        "Education": education_list,
        "Skills": normalize_skills(skills_raw),
    }


def parse_extracted_resume(payload: Any) -> ExtractedResume:
    """Validate normalized LLM payload into ExtractedResume."""
    normalized = normalize_llm_payload(payload)
    return ExtractedResume.model_validate(normalized)


def extract_json_from_text(text: str) -> dict:
    """Pull a JSON object from free-form LLM text."""
    text = text.strip()

    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed

    raise ValueError("No valid JSON object found in LLM response")


EXTRACTION_PROMPT = """You are an expert resume parser for a recruitment platform.

Extract ALL information from the resume text into the exact JSON schema below.
Rules:
- Return ONLY valid JSON. No markdown, no explanation.
- Email is REQUIRED when present in the resume — check the header/contact block carefully.
- Copy Email and Phone exactly as written (e.g. tejak.work@gmail.com, (507)400-4077).
- Use null for missing scalar fields.
- Use empty arrays [] for missing list fields — NEVER stringify arrays or objects.
- Professional_Experience and Education MUST be JSON arrays of objects, not strings.
- Responsibilities and Technologies Used MUST be JSON arrays of strings.
- Preserve dates as written on the resume (e.g. "Mar 2021", "Present", "2009 - 2013").
- For current roles, set "End Date" to "Present".
- Extract every job, education entry, and skill you can find.
- Split combined skill lines (e.g. "PHP • SQL • AWS") into separate array items.

Required JSON schema:
{{
  "Personal_Info": {{
    "Name": string | null,
    "Email": string | null,
    "Phone": string | null,
    "Location": string | null,
    "Current Company": string | null,
    "Current Designation": string | null
  }},
  "Professional_Experience": [
    {{
      "Company Name": string | null,
      "Job Title": string | null,
      "Employment Type": string | null,
      "Start Date": string | null,
      "End Date": string | null,
      "Responsibilities": [string],
      "Technologies Used": [string]
    }}
  ],
  "Education": [
    {{
      "Degree": string | null,
      "Specialisation": string | null,
      "College": string | null,
      "Start Year": string | null,
      "End Year": string | null,
      "Grade/CGPA": string | null
    }}
  ],
  "Skills": {{
    "Technical Skills": [string],
    "Soft Skills": [string]
  }}
}}

RESUME TEXT:
{resume_text}"""

PROFILE_EXTRACTION_PROMPT = """You are an expert resume parser. Extract ONLY personal info, education, and skills from this resume text.

Rules:
- Return ONLY valid JSON. No markdown.
- Email is REQUIRED when present — search the entire header/contact section (often near name and phone).
- Copy Email and Phone exactly as written on the resume.
- Use null for missing scalars, [] for missing lists.
- Extract every education entry and skill you can find.
- Split combined skill lines into separate array items.

Required JSON schema:
{{
  "Personal_Info": {{
    "Name": string | null,
    "Email": string | null,
    "Phone": string | null,
    "Location": string | null,
    "Current Company": string | null,
    "Current Designation": string | null
  }},
  "Education": [
    {{
      "Degree": string | null,
      "Specialisation": string | null,
      "College": string | null,
      "Start Year": string | null,
      "End Year": string | null,
      "Grade/CGPA": string | null
    }}
  ],
  "Skills": {{
    "Technical Skills": [string],
    "Soft Skills": [string]
  }}
}}

RESUME TEXT:
{resume_text}"""

EXPERIENCE_EXTRACTION_PROMPT = """You are an expert resume parser. Extract ONLY professional work experience from this resume text chunk.

Rules:
- Return ONLY valid JSON. No markdown.
- Professional_Experience MUST be a JSON array of objects.
- Extract every job in this chunk — do not skip roles.
- Preserve dates as written (e.g. "Mar 2021", "Present").
- Responsibilities and Technologies Used MUST be JSON arrays of strings.

Required JSON schema:
{{
  "Professional_Experience": [
    {{
      "Company Name": string | null,
      "Job Title": string | null,
      "Employment Type": string | null,
      "Start Date": string | null,
      "End Date": string | null,
      "Responsibilities": [string],
      "Technologies Used": [string]
    }}
  ]
}}

RESUME TEXT CHUNK:
{resume_text}"""
