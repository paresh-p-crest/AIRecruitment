"""Heuristic name/title/years extraction from resume headers and filenames."""

from __future__ import annotations

import re
from pathlib import Path

from contact_extract import EMAIL_PATTERN, extract_emails_from_text, extract_phones_from_text

_SECTION_HEADERS = {
    "PROFESSIONAL SUMMARY",
    "SUMMARY",
    "OBJECTIVE",
    "PROFILE",
    "EXPERIENCE",
    "WORK EXPERIENCE",
    "EDUCATION",
    "SKILLS",
    "TECHNICAL SKILLS",
    "CERTIFICATIONS",
    "PROJECTS",
    "CONTACT",
}

_TITLE_HINTS = (
    "developer",
    "engineer",
    "architect",
    "manager",
    "analyst",
    "consultant",
    "lead",
    "director",
    "specialist",
    "administrator",
    "designer",
    "scientist",
    "associate",
    "intern",
    "devops",
    "full stack",
    "fullstack",
    "data",
    "software",
    "senior",
    "sr.",
    "sr ",
    "junior",
    "jr.",
)

_YEARS_PATTERN = re.compile(
    r"(\d{1,2})\+?\s*years?(?:\s+of)?\s+experience",
    re.IGNORECASE,
)

_SKILLS_SECTION_START = re.compile(
    r"(?:^|\n)\s*(?:TECHNICAL\s+SKILLS?|CORE\s+COMPETENCIES|KEY\s+SKILLS|SKILLS)\s*[:\n]",
    re.IGNORECASE,
)
_NEXT_SECTION = re.compile(
    r"^\s*(?:PROFESSIONAL\s+EXPERIENCE|WORK\s+EXPERIENCE|EXPERIENCE|"
    r"EDUCATION|CERTIFICATIONS?|PROJECTS|ACADEMIC)\b",
    re.IGNORECASE,
)


def _clean_line(line: str) -> str:
    return " ".join((line or "").split())


def _looks_like_contact_line(line: str) -> bool:
    lowered = line.lower()
    if EMAIL_PATTERN.search(line):
        return True
    if extract_phones_from_text(line):
        return True
    if "linkedin.com" in lowered or "http://" in lowered or "https://" in lowered:
        return True
    if "|" in line and ("@" in line or re.search(r"\d{3}", line)):
        return True
    return False


def _looks_like_name(line: str) -> bool:
    cleaned = _clean_line(line)
    if not cleaned or len(cleaned) > 60:
        return False
    if cleaned.upper() in _SECTION_HEADERS:
        return False
    if _looks_like_contact_line(cleaned):
        return False
    if re.search(r"\d{3,}", cleaned):
        return False
    words = cleaned.replace(".", " ").split()
    if not 1 <= len(words) <= 5:
        return False
    if not re.match(r"^[\w\s\.\-'&]+$", cleaned, re.UNICODE):
        return False
    return True


def _looks_like_title(line: str) -> bool:
    cleaned = _clean_line(line)
    if not cleaned or len(cleaned) > 80:
        return False
    if cleaned.upper() in _SECTION_HEADERS:
        return False
    if _looks_like_contact_line(cleaned):
        return False
    lowered = cleaned.lower()
    return any(hint in lowered for hint in _TITLE_HINTS)


def _title_case_name(value: str) -> str:
    cleaned = _clean_line(value)
    if cleaned.isupper():
        return cleaned.title()
    return cleaned


def _strip_copy_suffix(stem: str) -> str:
    return re.sub(r"\s*\(\d+\)$", "", stem).strip()


def parse_name_title_from_filename(filename: str) -> tuple[str | None, str | None]:
    stem = _strip_copy_suffix(Path(filename or "").stem.strip())
    if not stem:
        return None, None

    if "_" in stem:
        name_part, title_part = stem.split("_", 1)
        name = _title_case_name(name_part.replace("-", " "))
        title = _clean_line(
            title_part.replace(".", " ").replace("-", " ").replace("resume", "").strip()
        )
        if _looks_like_name(name):
            return name, title or None

    for sep in (" - ", " – ", " — ", ", "):
        if sep in stem:
            left, right = stem.split(sep, 1)
            name = _title_case_name(left.replace("-", " "))
            title = _clean_line(right.replace("resume", "").strip())
            if _looks_like_name(name):
                return name, title or None

    if "." in stem:
        left, right = stem.rsplit(".", 1)
        name = _title_case_name(left.replace("-", " "))
        title = _clean_line(right.replace("-", " ").replace("resume", "").strip())
        if _looks_like_name(name) and (_looks_like_title(title) or len(title) >= 3):
            return name, title or None

    lowered = stem.lower()
    for hint in _TITLE_HINTS:
        idx = lowered.rfind(f" {hint}")
        if idx <= 0:
            continue
        name = _title_case_name(stem[:idx].replace("-", " "))
        title = _clean_line(stem[idx:].replace("resume", "").strip())
        if len(name.split()) <= 4 and _looks_like_name(name) and _looks_like_title(title):
            return name, title or None

    return None, None


def extract_name_from_text_header(text: str) -> str | None:
    lines = [_clean_line(line) for line in (text or "").splitlines()]
    lines = [line for line in lines if line]
    for line in lines[:12]:
        if _looks_like_name(line):
            return _title_case_name(line)
    return None


def extract_title_from_text_header(text: str, name: str | None = None) -> str | None:
    lines = [_clean_line(line) for line in (text or "").splitlines()]
    lines = [line for line in lines if line]
    start = 0
    if name:
        name_key = name.strip().lower()
        for index, line in enumerate(lines[:12]):
            if line.lower() == name_key or name_key in line.lower():
                start = index + 1
                break

    for line in lines[start : start + 6]:
        if _looks_like_title(line):
            return line
    return None


def extract_years_hint_from_text(text: str) -> float | None:
    match = _YEARS_PATTERN.search(text or "")
    if not match:
        return None
    years = float(match.group(1))
    return years if 0 < years <= 50 else None


def extract_skills_from_text_section(text: str) -> list[str]:
    """Parse TECHNICAL SKILLS / SKILLS blocks when the LLM returns none."""
    if not text:
        return []

    match = _SKILLS_SECTION_START.search(text)
    if not match:
        return []

    section = text[match.end() :]
    lines: list[str] = []
    for raw_line in section.splitlines():
        line = _clean_line(raw_line)
        if not line:
            if lines:
                break
            continue
        if _NEXT_SECTION.match(line):
            break
        lines.append(line)
        if len(lines) > 40:
            break

    if not lines:
        return []

    blob = " ".join(lines)
    parts = re.split(r"[\n\t|,;•●▪|]+", blob)
    skills: list[str] = []
    seen: set[str] = set()
    for part in parts:
        skill = part.strip(" -•\t:.")
        if not skill or len(skill) < 2 or len(skill) > 80:
            continue
        if skill.upper() in _SECTION_HEADERS:
            continue
        if re.fullmatch(r"\d{4}", skill):
            continue
        key = skill.lower()
        if key not in seen:
            seen.add(key)
            skills.append(skill)
    return skills[:150]
