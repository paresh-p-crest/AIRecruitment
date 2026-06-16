"""Rule-based resume scoring against a parsed job description (PRD Phase 4 weights)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from jd_parser import ParsedJobDescription

# PRD Phase 4.1 weights (must sum to 1.0)
WEIGHTS = {
    "skills": 0.35,
    "experience": 0.25,
    "projects": 0.15,
    "certifications": 0.10,
    "education": 0.15,
}

COMPONENT_LABELS = {
    "skills": "Skills Match",
    "experience": "Experience Match",
    "projects": "Project Relevance",
    "certifications": "Certification Relevance",
    "education": "Education Match",
}

CERT_KEYWORDS = (
    "certified",
    "certification",
    "certificate",
    "aws certified",
    "azure certified",
    "pmp",
    "scrum",
    "cka",
    "ckad",
)


@dataclass
class RedFlag:
    type: str
    description: str
    penalty: float


@dataclass
class ComponentBreakdownItem:
    key: str
    label: str
    weight_percent: float
    score: float
    weighted_points: float


@dataclass
class RuleMatchResult:
    component_scores: dict[str, float]
    component_breakdown: list[ComponentBreakdownItem]
    subtotal_score: float
    final_score: float
    matching_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    red_flags: list[RedFlag] = field(default_factory=list)
    red_flag_penalty: float = 0.0


def build_component_breakdown(component_scores: dict[str, float]) -> list[ComponentBreakdownItem]:
    """Build PRD-style per-component breakdown with weighted point contributions."""
    items: list[ComponentBreakdownItem] = []
    for key, weight in WEIGHTS.items():
        score = float(component_scores.get(key, 0.0))
        items.append(
            ComponentBreakdownItem(
                key=key,
                label=COMPONENT_LABELS[key],
                weight_percent=round(weight * 100, 1),
                score=round(score, 2),
                weighted_points=round(score * weight, 2),
            )
        )
    return items


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _token_variants(skill: str) -> list[str]:
    base = _normalize(skill)
    variants = {base}
    variants.add(re.sub(r"[^a-z0-9+#.\s]", "", base))
    if "/" in skill:
        for part in skill.split("/"):
            variants.add(_normalize(part))
    return [variant for variant in variants if len(variant) > 1]


def _skill_in_text(skill: str, corpus: str) -> bool:
    for variant in _token_variants(skill):
        if len(variant) <= 3:
            if re.search(rf"\b{re.escape(variant)}\b", corpus):
                return True
        elif variant in corpus:
            return True
    return False


def _collect_resume_skills(extracted: dict[str, Any]) -> list[str]:
    skills_block = extracted.get("Skills", {}) or {}
    technical = skills_block.get("Technical Skills") or []
    soft = skills_block.get("Soft Skills") or []
    return [str(item) for item in technical + soft if item]


def _collect_technologies(extracted: dict[str, Any]) -> list[str]:
    technologies: list[str] = []
    for entry in extracted.get("Professional_Experience", []) or []:
        for tech in entry.get("Technologies Used") or []:
            technologies.append(str(tech))
    return technologies


def _build_corpus(record) -> str:
    parts = [record.raw_text or ""]
    extracted = record.extracted_data or {}
    parts.extend(_collect_resume_skills(extracted))
    parts.extend(_collect_technologies(extracted))
    for entry in extracted.get("Professional_Experience", []) or []:
        parts.append(str(entry.get("Job Title") or ""))
        parts.extend(entry.get("Responsibilities") or [])
    for entry in extracted.get("Education", []) or []:
        parts.append(str(entry.get("Degree") or ""))
        parts.append(str(entry.get("Specialisation") or ""))
    return _normalize(" ".join(parts))


def _score_skills(
    jd: ParsedJobDescription, corpus: str, resume_skills: list[str]
) -> tuple[float, list[str], list[str]]:
    targets = jd.required_skills or []
    if not targets:
        keywords = re.findall(r"[A-Za-z][A-Za-z0-9+.#/\-]{1,}", jd.raw_text)
        targets = [word for word in keywords if len(word) > 2][:20]

    if not targets:
        return 50.0, [], []

    normalized_resume = _normalize(" ".join(resume_skills))
    matching: list[str] = []
    missing: list[str] = []

    for skill in targets:
        if _skill_in_text(skill, corpus) or _skill_in_text(skill, normalized_resume):
            matching.append(skill)
        else:
            missing.append(skill)

    ratio = len(matching) / len(targets)
    preferred_bonus = 0.0
    for skill in jd.preferred_skills:
        if _skill_in_text(skill, corpus):
            preferred_bonus += 2.0

    score = min(100.0, ratio * 100.0 + preferred_bonus)
    return round(score, 2), matching, missing


def _score_experience(
    jd: ParsedJobDescription, total_years: float
) -> float:
    if jd.min_years_experience is None:
        return 70.0 if total_years > 0 else 40.0

    minimum = jd.min_years_experience
    if total_years >= minimum:
        score = 100.0
        if jd.max_years_experience and total_years > jd.max_years_experience + 5:
            score = 85.0
    else:
        score = max(0.0, (total_years / minimum) * 100.0)

    return round(score, 2)


def _score_projects(jd: ParsedJobDescription, corpus: str) -> float:
    signals = (
        jd.responsibilities_text,
        jd.description,
        jd.requirements_text,
        " ".join(jd.required_skills),
    )
    keywords: list[str] = []
    for block in signals:
        if not block:
            continue
        keywords.extend(
            word
            for word in re.findall(r"[A-Za-z][A-Za-z0-9+.#\-]{2,}", block.lower())
            if len(word) > 3
        )

    if not keywords:
        return 60.0

    unique_keywords = list(dict.fromkeys(keywords))[:30]
    hits = sum(1 for word in unique_keywords if word in corpus)
    return round(min(100.0, (hits / len(unique_keywords)) * 100.0), 2)


def _score_certifications(corpus: str) -> float:
    hits = sum(1 for keyword in CERT_KEYWORDS if keyword in corpus)
    if hits >= 2:
        return 100.0
    if hits == 1:
        return 70.0
    return 35.0


def _score_education(jd: ParsedJobDescription, extracted: dict[str, Any]) -> float:
    education_entries = extracted.get("Education", []) or []
    if not education_entries:
        return 40.0

    education_text = _normalize(
        " ".join(
            f"{entry.get('Degree', '')} {entry.get('Specialisation', '')}"
            for entry in education_entries
        )
    )
    jd_text = _normalize(
        " ".join(
            filter(
                None,
                [jd.description, jd.requirements_text, " ".join(jd.required_skills)],
            )
        )
    )

    degree_keywords = ("bachelor", "master", "b.tech", "b.e", "m.tech", "mba", "phd")
    if any(keyword in education_text for keyword in degree_keywords):
        base = 80.0
    else:
        base = 55.0

    if jd_text and any(word in education_text for word in jd_text.split() if len(word) > 4):
        base = min(100.0, base + 15.0)

    return round(base, 2)


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip().lower()
    if normalized in {"present", "current", "now", "ongoing"}:
        return datetime.now()

    for fmt in ("%b %Y", "%B %Y", "%m/%Y", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue

    year_match = re.search(r"(19|20)\d{2}", normalized)
    if year_match:
        return datetime(int(year_match.group()), 1, 1)
    return None


def _detect_education_gap(extracted: dict[str, Any], experiences: list) -> RedFlag | None:
    """Flag unusual delay between graduation and first role (PRD education gap)."""
    education = extracted.get("Education", []) or []
    if not education or not experiences:
        return None

    grad_years: list[int] = []
    for entry in education:
        for field_name in ("End Year", "Start Year"):
            year_match = re.search(r"(19|20)\d{2}", str(entry.get(field_name) or ""))
            if year_match:
                grad_years.append(int(year_match.group()))
                break

    if not grad_years:
        return None

    latest_grad = max(grad_years)
    first_job_year: int | None = None
    for entry in experiences:
        start = _parse_date(entry.get("Start Date"))
        if start:
            first_job_year = start.year if first_job_year is None else min(first_job_year, start.year)

    if first_job_year and first_job_year - latest_grad > 3:
        return RedFlag(
            type="education_gap",
            description=(
                f"Graduation around {latest_grad} but first listed role starts around "
                f"{first_job_year} ({first_job_year - latest_grad} year gap)."
            ),
            penalty=5.0,
        )
    return None


def _detect_red_flags(extracted: dict[str, Any]) -> list[RedFlag]:
    """PRD Phase 3.1 red-flag detection with documented penalty ranges."""
    flags: list[RedFlag] = []
    personal = extracted.get("Personal_Info", {}) or {}
    experiences = extracted.get("Professional_Experience", []) or []

    has_email = bool(personal.get("Email"))
    has_phone = bool(personal.get("Phone"))
    if not has_email and not has_phone:
        flags.append(
            RedFlag(
                type="missing_contact",
                description="Missing email and phone number on resume.",
                penalty=2.0,
            )
        )

    dated_roles: list[tuple[datetime, datetime]] = []
    short_tenures = 0
    missing_dates = 0
    five_years_ago = datetime.now().replace(year=datetime.now().year - 5)
    recent_job_count = 0

    for entry in experiences:
        start = _parse_date(entry.get("Start Date"))
        end = _parse_date(entry.get("End Date"))
        if not start or not end:
            missing_dates += 1
            continue
        dated_roles.append((start, end))
        months = (end - start).days / 30.44
        if months < 12:
            short_tenures += 1
        if start >= five_years_ago or end >= five_years_ago:
            recent_job_count += 1

    if missing_dates:
        flags.append(
            RedFlag(
                type="missing_dates",
                description=f"{missing_dates} employment entries lack start or end dates.",
                penalty=5.0,
            )
        )

    dated_roles.sort(key=lambda item: item[0])
    for index in range(1, len(dated_roles)):
        gap_days = (dated_roles[index][0] - dated_roles[index - 1][1]).days
        if gap_days > 92:
            gap_months = gap_days // 30
            flags.append(
                RedFlag(
                    type="employment_gap",
                    description=f"Employment gap of about {gap_months} months detected.",
                    penalty=round(min(10.0, max(5.0, 5.0 + gap_months)), 1),
                )
            )
            break

    if short_tenures >= 2 or recent_job_count > 2:
        flags.append(
            RedFlag(
                type="job_hopping",
                description=(
                    f"{short_tenures} role(s) under 12 months"
                    + (
                        f" and {recent_job_count} job changes in the last 5 years."
                        if recent_job_count > 2
                        else "."
                    )
                ),
                penalty=10.0,
            )
        )

    education_gap = _detect_education_gap(extracted, experiences)
    if education_gap:
        flags.append(education_gap)

    return flags


def score_resume_against_jd(record, jd: ParsedJobDescription) -> RuleMatchResult:
    """Compute weighted rule-based match score for one resume record."""
    extracted = record.extracted_data or {}
    metrics = record.calculated_metrics or {}
    total_years = float(metrics.get("Total_Years_Of_Experience") or 0.0)
    corpus = _build_corpus(record)
    resume_skills = _collect_resume_skills(extracted)

    skills_score, matching, missing = _score_skills(jd, corpus, resume_skills)
    experience_score = _score_experience(jd, total_years)
    projects_score = _score_projects(jd, corpus)
    certifications_score = _score_certifications(corpus)
    education_score = _score_education(jd, extracted)

    component_scores = {
        "skills": skills_score,
        "experience": experience_score,
        "projects": projects_score,
        "certifications": certifications_score,
        "education": education_score,
    }

    rounded_scores = {key: round(value, 2) for key, value in component_scores.items()}
    breakdown = build_component_breakdown(rounded_scores)
    subtotal = round(sum(item.weighted_points for item in breakdown), 2)
    red_flags = _detect_red_flags(extracted)
    penalty = min(20.0, sum(flag.penalty for flag in red_flags))
    final_score = round(max(0.0, min(100.0, subtotal - penalty)), 2)

    return RuleMatchResult(
        component_scores=rounded_scores,
        component_breakdown=breakdown,
        subtotal_score=subtotal,
        final_score=final_score,
        matching_skills=matching,
        missing_skills=missing,
        red_flags=red_flags,
        red_flag_penalty=round(penalty, 2),
    )
