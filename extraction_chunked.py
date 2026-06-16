"""Multi-pass LLM extraction for long resumes (avoids Bedrock timeouts)."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from llm_factory import build_llm_from_settings
from contact_extract import (
    extract_emails_from_text,
    extract_phones_from_text,
    normalize_email,
)
from resume_parser import (
    EXPERIENCE_EXTRACTION_PROMPT,
    PROFILE_EXTRACTION_PROMPT,
    extract_json_from_text,
)
from schemas import (
    ExperienceExtraction,
    ExtractedResume,
    PersonalInfo,
    ProfessionalExperienceEntry,
    ProfileExtraction,
    Skills,
)
from settings_service import get_active_model_name, get_effective_settings

logger = logging.getLogger(__name__)

CHUNK_THRESHOLD = int(os.getenv("EXTRACTION_CHUNK_THRESHOLD", "9000"))
CHUNK_SIZE = int(os.getenv("EXTRACTION_CHUNK_SIZE", "6500"))
CHUNK_OVERLAP = int(os.getenv("EXTRACTION_CHUNK_OVERLAP", "400"))
PROFILE_HEAD_CHARS = int(os.getenv("EXTRACTION_PROFILE_CHARS", "12000"))


def should_use_chunked_extraction(text: str) -> bool:
    if os.getenv("DISABLE_CHUNKED_EXTRACTION", "").lower() in {"1", "true", "yes"}:
        return False
    return len(text) > CHUNK_THRESHOLD


def split_text_chunks(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks


def _experience_key(entry: ProfessionalExperienceEntry) -> tuple[str, str, str]:
    return (
        (entry.company_name or "").strip().lower(),
        (entry.job_title or "").strip().lower(),
        (entry.start_date or "").strip().lower(),
    )


def _dedupe_experiences(
    entries: list[ProfessionalExperienceEntry],
) -> list[ProfessionalExperienceEntry]:
    seen: set[tuple[str, str, str]] = set()
    merged: list[ProfessionalExperienceEntry] = []
    for entry in entries:
        key = _experience_key(entry)
        if key in seen and any(key):
            continue
        seen.add(key)
        merged.append(entry)
    return merged


def _merge_skills(primary: Skills, secondary: Skills) -> Skills:
    tech = list(
        dict.fromkeys(
            [s for s in primary.technical_skills if s]
            + [s for s in secondary.technical_skills if s]
        )
    )
    soft = list(
        dict.fromkeys(
            [s for s in primary.soft_skills if s]
            + [s for s in secondary.soft_skills if s]
        )
    )
    return Skills(technical_skills=tech, soft_skills=soft)


def _merge_profile_parts(profiles: list[ProfileExtraction]) -> ProfileExtraction:
    if not profiles:
        return ProfileExtraction()

    best_personal = PersonalInfo()
    for profile in profiles:
        info = profile.personal_info
        if info.name and not best_personal.name:
            best_personal = info
            break

    for profile in profiles:
        info = profile.personal_info
        updates: dict[str, Any] = {}
        for field in (
            "name",
            "email",
            "phone",
            "location",
            "current_company",
            "current_designation",
        ):
            if not getattr(best_personal, field) and getattr(info, field):
                updates[field] = getattr(info, field)
        if updates:
            best_personal = best_personal.model_copy(update=updates)

    education_seen: set[tuple[str, str, str]] = set()
    education: list = []
    for profile in profiles:
        for entry in profile.education:
            key = (
                (entry.degree or "").lower(),
                (entry.college or "").lower(),
                (entry.end_year or "").lower(),
            )
            if key in education_seen and any(key):
                continue
            education_seen.add(key)
            education.append(entry)

    skills = Skills()
    for profile in profiles:
        skills = _merge_skills(skills, profile.skills)

    return ProfileExtraction(
        personal_info=best_personal,
        education=education,
        skills=skills,
    )


def _backfill_contact_from_text(
    resume: ExtractedResume, raw_text: str
) -> ExtractedResume:
    """Fill missing email/phone on chunked profile output from raw text."""
    personal = resume.personal_info.model_copy()
    updated = False

    if not normalize_email(personal.email):
        emails = extract_emails_from_text(raw_text)
        if emails:
            personal.email = normalize_email(emails[0])
            updated = True

    if not personal.phone:
        phones = extract_phones_from_text(raw_text)
        if phones:
            personal.phone = phones[0]
            updated = True

    if not updated:
        return resume

    return ExtractedResume(
        personal_info=personal,
        professional_experience=list(resume.professional_experience),
        education=list(resume.education),
        skills=resume.skills,
    )


def _build_extracted_resume(
    profile: ProfileExtraction,
    experiences: list[ProfessionalExperienceEntry],
) -> ExtractedResume:
    return ExtractedResume(
        personal_info=profile.personal_info,
        professional_experience=_dedupe_experiences(experiences),
        education=profile.education,
        skills=profile.skills,
    )


async def _invoke_structured(llm, schema: type, prompt: str):
    structured = llm.with_structured_output(schema)
    return await structured.ainvoke(prompt)


async def _invoke_json_fallback(llm, prompt: str) -> dict:
    from llm_usage import get_usage

    response = await llm.ainvoke(prompt)
    usage = get_usage()
    if usage is not None:
        usage.add_response(response)
    content = getattr(response, "content", str(response))
    if isinstance(content, list):
        content = " ".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return extract_json_from_text(str(content))


def _profile_is_empty(profile: ProfileExtraction) -> bool:
    """Bedrock structured output can return schema-valid but empty objects."""
    personal = profile.personal_info
    return (
        not personal.name
        and not personal.email
        and not personal.phone
        and not profile.education
        and not profile.skills.technical_skills
        and not profile.skills.soft_skills
    )


def _profile_is_incomplete(profile: ProfileExtraction) -> bool:
    """Structured output may return education while omitting skills or contact info."""
    if _profile_is_empty(profile):
        return True
    if not profile.skills.technical_skills and not profile.skills.soft_skills:
        return True
    personal = profile.personal_info
    if not personal.name and not personal.email:
        return True
    return False


def _profile_from_payload(payload: dict) -> ProfileExtraction:
    return ProfileExtraction.model_validate(
        {
            "Personal_Info": payload.get("Personal_Info")
            or payload.get("personal_info")
            or {},
            "Education": payload.get("Education") or payload.get("education") or [],
            "Skills": payload.get("Skills") or payload.get("skills") or {},
        }
    )


async def _extract_profile_from_json(llm, prompt: str) -> ProfileExtraction:
    payload = await _invoke_json_fallback(llm, prompt)
    return _profile_from_payload(payload)


async def _extract_profile(
    llm, text: str, *, prefer_json: bool = False
) -> ProfileExtraction:
    head = text[:PROFILE_HEAD_CHARS]
    prompt = PROFILE_EXTRACTION_PROMPT.format(resume_text=head)
    if prefer_json:
        return await _extract_profile_from_json(llm, prompt)

    structured_profile: ProfileExtraction | None = None
    try:
        result = await _invoke_structured(llm, ProfileExtraction, prompt)
        structured_profile = ProfileExtraction.model_validate(result)
        if not _profile_is_incomplete(structured_profile):
            return structured_profile
        logger.info("Structured profile incomplete; augmenting with JSON fallback")
    except (ValidationError, ValueError, TypeError) as exc:
        logger.info("Structured profile failed (%s); using JSON fallback", exc)

    json_profile = await _extract_profile_from_json(llm, prompt)
    if structured_profile and not _profile_is_empty(structured_profile):
        return _merge_profile_parts([structured_profile, json_profile])
    return json_profile


async def _extract_experience_chunk(
    llm, chunk: str, *, prefer_json: bool = False
) -> list[ProfessionalExperienceEntry]:
    prompt = EXPERIENCE_EXTRACTION_PROMPT.format(resume_text=chunk)
    if prefer_json:
        payload = await _invoke_json_fallback(llm, prompt)
        parsed = ExperienceExtraction.model_validate(payload)
        return list(parsed.professional_experience)

    try:
        result = await _invoke_structured(llm, ExperienceExtraction, prompt)
        parsed = ExperienceExtraction.model_validate(result)
        if parsed.professional_experience:
            return list(parsed.professional_experience)
        logger.debug("Structured experience chunk was empty; using JSON fallback")
    except (ValidationError, ValueError, TypeError) as exc:
        logger.debug("Structured experience chunk failed (%s); using JSON fallback", exc)
    payload = await _invoke_json_fallback(llm, prompt)
    parsed = ExperienceExtraction.model_validate(payload)
    return list(parsed.professional_experience)


async def extract_resume_data_chunked(
    cleaned_text: str,
    db: AsyncSession,
) -> ExtractedResume:
    """Run profile + per-chunk experience extraction, then merge."""
    settings = await get_effective_settings(db)
    llm = build_llm_from_settings(settings)
    provider_label = f"{settings.llm_provider} ({get_active_model_name(settings)})"
    prefer_json = settings.llm_provider == "aws_bedrock"

    chunks = split_text_chunks(cleaned_text)
    logger.info(
        "Chunked extraction: %d chars → %d chunk(s) via %s",
        len(cleaned_text),
        len(chunks),
        provider_label,
    )

    errors: list[str] = []

    try:
        profile = await _extract_profile(llm, cleaned_text, prefer_json=prefer_json)
    except Exception as exc:
        errors.append(f"profile pass: {exc}")
        profile = ProfileExtraction()

    all_experience: list[ProfessionalExperienceEntry] = []
    for index, chunk in enumerate(chunks):
        try:
            entries = await _extract_experience_chunk(llm, chunk, prefer_json=prefer_json)
            all_experience.extend(entries)
            logger.debug(
                "Experience chunk %d/%d: %d roles",
                index + 1,
                len(chunks),
                len(entries),
            )
        except Exception as exc:
            errors.append(f"experience chunk {index + 1}: {exc}")

    if not profile.personal_info.name and not all_experience and errors:
        raise RuntimeError(
            f"Chunked extraction failed using {provider_label}. "
            + " | ".join(errors)
        )

    merged = _build_extracted_resume(profile, all_experience)
    merged = _backfill_contact_from_text(merged, cleaned_text)
    if errors:
        logger.warning(
            "Chunked extraction completed with partial errors: %s",
            " | ".join(errors),
        )
    return merged
