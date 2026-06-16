"""Persist and load job descriptions — multiple postings with one active."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jd_parser import ParsedJobDescription, parse_job_description
from models import JobDescription, MatchResult
from schemas import (
    JobDescriptionCreate,
    JobDescriptionListItem,
    JobDescriptionPublic,
    JobDescriptionUpdate,
)

SAMPLE_JOB_DESCRIPTION = """Senior Data Engineer/Team Lead

Min. 6 Years
AWS
MS Azure
Data Pipelines
Python
ETL

Description

We are looking for a skilled Senior Data Engineer with strong expertise in SQL, Python, and ETL processes. The ideal candidate will build and optimize data pipelines, manage data workflows using tools like Airflow, and work with cloud platforms such as AWS or Azure.

You will collaborate with business stakeholders to translate requirements into scalable data solutions, ensure data quality and performance, and support data-driven decision-making. Strong communication, documentation, and the ability to handle fast-paced environments are essential.

Requirements

• 6+ years of experience in Data Engineering or similar role
• Strong expertise in SQL (stored procedures, views, indexing, data warehouse design)
• Proficiency in Python (ETL, automation, pandas)
• Hands-on experience with Airflow or similar orchestration tools
• Experience with AWS or Azure cloud platforms
• Proven experience leading or coordinating small technical teams
• Strong experience in SQL-heavy projects, preferably in financial services
• Experience with mortgage, lending, or structured finance data is a plus
• Familiarity with Kafka, NiFi, Snowflake, or Databricks is a plus
• Strong Git/version control practices
• Experience building or maintaining data dictionaries
• Ability to translate business workflows into technical requirements
• Strong communication and documentation skills

Responsibilities

• Design, build, and optimize ETL pipelines and data workflows
• Develop and maintain efficient SQL queries and data warehouse solutions
• Orchestrate and monitor workflows using Airflow or similar tools
• Collaborate with business and operations teams to define technical requirements
• Ensure data quality, performance, and reliability
• Maintain clear documentation (data flows, definitions, logic)
"""


def is_valid_for_matching(
    raw_text: str, parsed: ParsedJobDescription | None = None
) -> bool:
    """JD must have enough text and parseable criteria (skills, years, or requirements)."""
    text = (raw_text or "").strip()
    if len(text) < 40:
        return False
    jd = parsed if parsed is not None else parse_job_description(text)
    return bool(
        jd.required_skills
        or jd.preferred_skills
        or jd.min_years_experience is not None
        or (jd.requirements_text and len(jd.requirements_text.strip()) >= 20)
        or (jd.description and len(jd.description.strip()) >= 20)
    )


def parsed_to_dict(parsed: ParsedJobDescription) -> dict:
    return {
        "job_title": parsed.job_title,
        "min_years_experience": parsed.min_years_experience,
        "max_years_experience": parsed.max_years_experience,
        "required_skills": parsed.required_skills,
        "preferred_skills": parsed.preferred_skills,
        "description": parsed.description,
        "requirements_text": parsed.requirements_text,
        "responsibilities_text": parsed.responsibilities_text,
    }


def derive_job_title(raw_text: str, parsed: ParsedJobDescription | None = None) -> str:
    jd = parsed if parsed is not None else parse_job_description(raw_text)
    if jd.job_title:
        return _normalize_title(jd.job_title)
    skip_prefixes = ("min.", "description", "requirements", "responsibilities")
    for line in (raw_text or "").splitlines():
        cleaned = line.strip()
        if not cleaned or len(cleaned) < 3:
            continue
        lower = cleaned.lower()
        if any(lower.startswith(prefix) for prefix in skip_prefixes):
            continue
        return _normalize_title(cleaned)
    return "Untitled role"


def _normalize_title(value: str) -> str:
    """Single-line display title (max 80 chars)."""
    single = " ".join((value or "").split())
    if not single:
        return "Untitled role"
    return single[:80]


def format_job_list_label(title: str, match_count: int, *, is_active: bool) -> str:
    label = _normalize_title(title)
    if len(label) > 52:
        label = f"{label[:51]}…"
    prefix = "★ " if is_active else ""
    return f"{prefix}{label} ({match_count} match{'es' if match_count != 1 else ''})"


async def _match_counts_by_job(session: AsyncSession) -> dict[int, int]:
    rows = await session.execute(
        select(MatchResult.job_description_id, func.count())
        .group_by(MatchResult.job_description_id)
    )
    return {job_id: count for job_id, count in rows.all()}


def _row_to_public(
    row: JobDescription,
    *,
    match_count: int = 0,
) -> JobDescriptionPublic:
    raw = row.raw_text or ""
    parsed = parse_job_description(raw)
    return JobDescriptionPublic(
        id=row.id,
        title=row.title or derive_job_title(raw, parsed),
        raw_text=raw,
        parsed=parsed_to_dict(parsed),
        is_active=row.is_active,
        created_at=row.created_at,
        updated_at=row.updated_at,
        has_content=bool(raw.strip()),
        is_valid_for_matching=is_valid_for_matching(raw, parsed),
        match_count=match_count,
    )


async def ensure_job_description_row(session: AsyncSession) -> JobDescription:
    """Ensure at least one job exists and return the active posting."""
    return await get_active_job_row(session)


async def get_active_job_row(session: AsyncSession) -> JobDescription:
    result = await session.execute(
        select(JobDescription)
        .where(JobDescription.is_active.is_(True))
        .order_by(JobDescription.id.desc())
    )
    row = result.scalar_one_or_none()
    if row:
        return row

    any_result = await session.execute(
        select(JobDescription).order_by(JobDescription.id.asc())
    )
    row = any_result.scalar_one_or_none()
    if row:
        row.is_active = True
        row.updated_at = datetime.now(timezone.utc)
        await session.flush()
        return row

    row = JobDescription(
        title="Untitled role",
        raw_text="",
        is_active=True,
    )
    session.add(row)
    await session.flush()
    return row


async def get_job_description(
    session: AsyncSession, job_id: int | None = None
) -> JobDescriptionPublic:
    if job_id is None:
        row = await get_active_job_row(session)
    else:
        row = await session.get(JobDescription, job_id)
        if not row:
            raise ValueError(f"Job description with id {job_id} not found.")

    counts = await _match_counts_by_job(session)
    return _row_to_public(row, match_count=counts.get(row.id, 0))


async def list_job_descriptions(session: AsyncSession) -> list[JobDescriptionListItem]:
    result = await session.execute(
        select(JobDescription).order_by(
            JobDescription.is_active.desc(),
            JobDescription.updated_at.desc(),
        )
    )
    rows = result.scalars().all()
    counts = await _match_counts_by_job(session)
    items: list[JobDescriptionListItem] = []
    for row in rows:
        raw = row.raw_text or ""
        parsed = parse_job_description(raw)
        items.append(
            JobDescriptionListItem(
                id=row.id,
                title=row.title or derive_job_title(raw, parsed),
                is_active=row.is_active,
                is_valid_for_matching=is_valid_for_matching(raw, parsed),
                match_count=counts.get(row.id, 0),
                updated_at=row.updated_at,
                created_at=row.created_at,
            )
        )
    return items


async def update_job_description(
    session: AsyncSession,
    payload: JobDescriptionUpdate,
    job_id: int | None = None,
) -> JobDescriptionPublic:
    row = await get_active_job_row(session) if job_id is None else await session.get(
        JobDescription, job_id
    )
    if not row:
        raise ValueError(f"Job description with id {job_id} not found.")

    row.raw_text = (payload.raw_text or "").strip()
    parsed = parse_job_description(row.raw_text)
    row.title = _normalize_title(payload.title or derive_job_title(row.raw_text, parsed))
    row.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return await get_job_description(session, row.id)


async def create_job_description(
    session: AsyncSession, payload: JobDescriptionCreate
) -> JobDescriptionPublic:
    raw = (payload.raw_text or "").strip()
    parsed = parse_job_description(raw)
    title = _normalize_title(payload.title or derive_job_title(raw, parsed))

    if payload.set_as_active:
        active_rows = await session.execute(
            select(JobDescription).where(JobDescription.is_active.is_(True))
        )
        for active in active_rows.scalars().all():
            active.is_active = False

    row = JobDescription(
        title=title,
        raw_text=raw,
        is_active=payload.set_as_active,
    )
    session.add(row)
    await session.flush()
    return await get_job_description(session, row.id)


async def activate_job_description(
    session: AsyncSession, job_id: int
) -> JobDescriptionPublic:
    row = await session.get(JobDescription, job_id)
    if not row:
        raise ValueError(f"Job description with id {job_id} not found.")

    active_rows = await session.execute(
        select(JobDescription).where(JobDescription.is_active.is_(True))
    )
    for active in active_rows.scalars().all():
        active.is_active = False

    row.is_active = True
    row.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return await get_job_description(session, row.id)


async def delete_job_description(session: AsyncSession, job_id: int) -> dict:
    """
    Delete a job posting and its match results only.

    Candidate profiles and resume files are not affected.
    """
    row = await session.get(JobDescription, job_id)
    if not row:
        raise ValueError(f"Job description with id {job_id} not found.")

    was_active = row.is_active
    title = row.title or derive_job_title(row.raw_text or "")

    delete_result = await session.execute(
        delete(MatchResult).where(MatchResult.job_description_id == job_id)
    )
    matches_removed = delete_result.rowcount or 0

    await session.delete(row)
    await session.flush()

    remaining = await session.execute(
        select(JobDescription).order_by(JobDescription.updated_at.desc())
    )
    survivors = list(remaining.scalars().all())

    new_active_id: int | None = None
    if not survivors:
        replacement = JobDescription(
            title="Untitled role",
            raw_text="",
            is_active=True,
        )
        session.add(replacement)
        await session.flush()
        new_active_id = replacement.id
    elif was_active:
        survivors[0].is_active = True
        survivors[0].updated_at = datetime.now(timezone.utc)
        new_active_id = survivors[0].id
        await session.flush()
    else:
        active = await session.execute(
            select(JobDescription).where(JobDescription.is_active.is_(True))
        )
        active_row = active.scalar_one_or_none()
        new_active_id = active_row.id if active_row else None

    return {
        "deleted_job_id": job_id,
        "deleted_title": title,
        "matches_removed": matches_removed,
        "candidates_preserved": True,
        "new_active_job_id": new_active_id,
    }
