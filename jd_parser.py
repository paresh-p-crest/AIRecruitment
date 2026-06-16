"""Parse free-text job descriptions (JD.txt style) into structured criteria."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

SECTION_HEADERS = {
    "description",
    "requirements",
    "responsibilities",
    "natural abilities",
    "preferred qualifications",
    "qualifications",
}

MIN_YEARS_PATTERNS = (
    re.compile(r"(?:min\.?|minimum)\s*(\d+)\s*(?:\+?\s*)?years?", re.I),
    re.compile(r"(\d+)\s*\+\s*years?", re.I),
    re.compile(r"(\d+)\s*years?\s*(?:of\s+)?experience", re.I),
)

MAX_YEARS_PATTERN = re.compile(
    r"(?:max\.?|maximum|up\s+to)\s*(\d+)\s*years?", re.I
)

PREFERRED_MARKERS = (
    "is a plus",
    "nice to have",
    "preferred",
    "familiarity with",
    "bonus",
    "optional",
)


@dataclass
class ParsedJobDescription:
    job_title: str | None = None
    min_years_experience: float | None = None
    max_years_experience: float | None = None
    required_skills: list[str] = field(default_factory=list)
    preferred_skills: list[str] = field(default_factory=list)
    description: str | None = None
    requirements_text: str | None = None
    responsibilities_text: str | None = None
    raw_text: str = ""


def _is_section_header(line: str) -> bool:
    normalized = line.strip().rstrip(":").lower()
    return normalized in SECTION_HEADERS


def _extract_years(line: str) -> tuple[float | None, float | None]:
    min_years: float | None = None
    max_years: float | None = None

    for pattern in MIN_YEARS_PATTERNS:
        match = pattern.search(line)
        if match:
            min_years = float(match.group(1))
            break

    max_match = MAX_YEARS_PATTERN.search(line)
    if max_match:
        max_years = float(max_match.group(1))

    return min_years, max_years


def _clean_bullet(line: str) -> str:
    return re.sub(r"^[\s•●▪◦\-–—*]+", "", line).strip()


def _is_preferred_line(line: str) -> bool:
    lowered = line.lower()
    return any(marker in lowered for marker in PREFERRED_MARKERS)


def _split_skill_tokens(line: str) -> list[str]:
    if not line or _is_section_header(line):
        return []

    cleaned = _clean_bullet(line)
    if not cleaned or len(cleaned) > 120:
        return []

    if "," in cleaned:
        parts = [part.strip() for part in cleaned.split(",")]
    elif " / " in cleaned:
        parts = [part.strip() for part in cleaned.split(" / ")]
    else:
        parts = [cleaned]

    return [part for part in parts if part and len(part) > 1]


def parse_job_description(raw_text: str) -> ParsedJobDescription:
    """Parse a pasted JD into title, experience range, and skill lists."""
    text = raw_text.strip()
    parsed = ParsedJobDescription(raw_text=text)
    if not text:
        return parsed

    lines = [line.strip() for line in text.splitlines()]
    non_empty = [line for line in lines if line]

    if not non_empty:
        return parsed

    parsed.job_title = non_empty[0]

    header_skills: list[str] = []
    current_section: str | None = None
    section_buffers: dict[str, list[str]] = {
        "description": [],
        "requirements": [],
        "responsibilities": [],
    }

    for line in non_empty[1:]:
        if _is_section_header(line):
            current_section = line.strip().rstrip(":").lower()
            continue

        if current_section is None:
            min_years, max_years = _extract_years(line)
            if min_years is not None and parsed.min_years_experience is None:
                parsed.min_years_experience = min_years
            if max_years is not None and parsed.max_years_experience is None:
                parsed.max_years_experience = max_years

            if min_years is None and max_years is None:
                header_skills.extend(_split_skill_tokens(line))
            continue

        if current_section in section_buffers:
            section_buffers[current_section].append(line)

        min_years, max_years = _extract_years(line)
        if min_years is not None and parsed.min_years_experience is None:
            parsed.min_years_experience = min_years
        if max_years is not None and parsed.max_years_experience is None:
            parsed.max_years_experience = max_years

    parsed.description = "\n".join(section_buffers["description"]).strip() or None
    parsed.requirements_text = "\n".join(section_buffers["requirements"]).strip() or None
    parsed.responsibilities_text = (
        "\n".join(section_buffers["responsibilities"]).strip() or None
    )

    required: list[str] = []
    preferred: list[str] = []

    for skill in header_skills:
        if _is_preferred_line(skill):
            preferred.append(_clean_bullet(skill))
        else:
            required.append(skill)

    req_lines = section_buffers["requirements"] or []
    for line in req_lines:
        cleaned = _clean_bullet(line)
        if not cleaned:
            continue
        if _is_preferred_line(cleaned):
            preferred.append(cleaned)
        elif cleaned.startswith(("•", "-", "●", "▪", "◦")) or len(cleaned) > 3:
            required.append(cleaned)

    parsed.required_skills = _dedupe_skills(required)
    parsed.preferred_skills = _dedupe_skills(preferred)

    if parsed.min_years_experience is None:
        for line in non_empty:
            min_years, max_years = _extract_years(line)
            if min_years is not None:
                parsed.min_years_experience = min_years
            if max_years is not None:
                parsed.max_years_experience = max_years

    return parsed


def _dedupe_skills(skills: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for skill in skills:
        key = skill.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(skill)
    return unique
