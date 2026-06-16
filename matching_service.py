"""Orchestrate hybrid matching for all stored resumes."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jd_parser import parse_job_description
from jd_service import get_active_job_row, get_job_description, is_valid_for_matching
from matching_engine import build_component_breakdown, score_resume_against_jd
from matching_llm import generate_match_narrative
from models import Candidate, JobDescription, MatchResult, ResumeRecord
from schemas import ComponentScoreBreakdown, MatchResultDetail, MatchRunResponse


async def _recalculate_ranks(db: AsyncSession, job_description_id: int) -> None:
    result = await db.execute(
        select(MatchResult).where(MatchResult.job_description_id == job_description_id)
    )
    matches = list(result.scalars().all())
    for index, match in enumerate(
        sorted(matches, key=lambda item: item.final_score, reverse=True), start=1
    ):
        match.rank = index


def _record_for_matching(candidate: Candidate, record: ResumeRecord):
    """Scoring view: candidate profile data with resume metadata (no ORM mutation)."""
    from types import SimpleNamespace

    return SimpleNamespace(
        id=record.id,
        filename=record.filename,
        raw_text=record.raw_text or "",
        extracted_data=candidate.extracted_data or record.extracted_data,
        calculated_metrics=candidate.calculated_metrics or record.calculated_metrics,
    )


async def _upsert_match_for_record(
    db: AsyncSession,
    record: ResumeRecord,
    parsed_jd,
    *,
    job_description_id: int,
    include_llm: bool,
    candidate: Candidate | None = None,
) -> MatchResult:
    scoring_record = (
        _record_for_matching(candidate, record) if candidate else record
    )
    rule_result = score_resume_against_jd(scoring_record, parsed_jd)
    narrative = {"strengths": [], "weaknesses": [], "summary": ""}

    if include_llm:
        try:
            narrative = await generate_match_narrative(
                db, parsed_jd, scoring_record, rule_result
            )
        except Exception:
            narrative = {
                "strengths": [],
                "weaknesses": [],
                "summary": "AI narrative unavailable — rule-based score only.",
            }

    personal = (scoring_record.extracted_data or {}).get("Personal_Info", {}) or {}
    if candidate:
        existing = await db.execute(
            select(MatchResult).where(
                MatchResult.candidate_id == candidate.id,
                MatchResult.job_description_id == job_description_id,
            )
        )
    else:
        existing = await db.execute(
            select(MatchResult).where(
                MatchResult.resume_id == record.id,
                MatchResult.job_description_id == job_description_id,
            )
        )
    match = existing.scalar_one_or_none()

    if match is None:
        match = MatchResult(
            resume_id=record.id,
            candidate_id=candidate.id if candidate else None,
            job_description_id=job_description_id,
        )
        db.add(match)

    match.candidate_id = candidate.id if candidate else match.candidate_id
    match.resume_id = record.id
    match.job_description_id = job_description_id
    match.candidate_name = personal.get("Name") or (
        f"{candidate.first_name or ''} {candidate.last_name or ''}".strip()
        if candidate
        else None
    )
    match.filename = record.filename
    match.final_score = rule_result.final_score
    match.component_scores = rule_result.component_scores
    match.matching_skills = rule_result.matching_skills
    match.missing_skills = rule_result.missing_skills
    match.red_flags = [
        {
            "type": flag.type,
            "description": flag.description,
            "penalty": flag.penalty,
        }
        for flag in rule_result.red_flags
    ]
    match.red_flag_penalty = rule_result.red_flag_penalty
    match.strengths = narrative.get("strengths") or []
    match.weaknesses = narrative.get("weaknesses") or []
    match.summary = narrative.get("summary") or ""
    match.matched_at = datetime.now(timezone.utc)
    return match


async def _require_parsed_jd(db: AsyncSession, job_id: int | None = None):
    if job_id is None:
        jd_row = await get_active_job_row(db)
    else:
        jd_row = await db.get(JobDescription, job_id)
        if not jd_row:
            raise ValueError(f"Job description with id {job_id} not found.")

    raw = jd_row.raw_text or ""
    if not raw.strip():
        raise ValueError(
            "Job description is empty. Add a job description on the Job Description tab before matching."
        )
    parsed = parse_job_description(raw)
    if not is_valid_for_matching(raw, parsed):
        raise ValueError(
            "Job description is incomplete. Add a title, skills, experience years, or requirements before matching."
        )
    return jd_row, parsed


def _default_resume_for_candidate(candidate: Candidate) -> ResumeRecord | None:
    if not candidate.resumes:
        return None
    return next(
        (r for r in candidate.resumes if r.is_default),
        candidate.resumes[0],
    )


async def _existing_match_keys(
    db: AsyncSession, job_description_id: int
) -> tuple[set[int], set[int]]:
    """Return (matched_candidate_ids, matched_resume_ids) for a job."""
    result = await db.execute(
        select(MatchResult.candidate_id, MatchResult.resume_id).where(
            MatchResult.job_description_id == job_description_id
        )
    )
    candidate_ids: set[int] = set()
    resume_ids: set[int] = set()
    for candidate_id, resume_id in result.all():
        if candidate_id:
            candidate_ids.add(candidate_id)
        if resume_id:
            resume_ids.add(resume_id)
    return candidate_ids, resume_ids


async def run_matching(
    db: AsyncSession,
    *,
    include_llm: bool = True,
    job_id: int | None = None,
    rematch_all: bool = False,
) -> MatchRunResponse:
    jd_row, parsed_jd = await _require_parsed_jd(db, job_id)
    result = await db.execute(
        select(Candidate)
        .options(selectinload(Candidate.resumes))
        .order_by(Candidate.id)
    )
    candidates = result.scalars().unique().all()

    if not candidates:
        raise ValueError("No candidates uploaded yet. Upload candidates before matching.")

    if rematch_all:
        await db.execute(
            delete(MatchResult).where(MatchResult.job_description_id == jd_row.id)
        )
        matched_candidate_ids: set[int] = set()
        matched_resume_ids: set[int] = set()
    else:
        matched_candidate_ids, matched_resume_ids = await _existing_match_keys(
            db, jd_row.id
        )

    matched_new = 0
    skipped_existing = 0

    for candidate in candidates:
        record = _default_resume_for_candidate(candidate)
        if not record:
            continue

        already_matched = (
            candidate.id in matched_candidate_ids or record.id in matched_resume_ids
        )
        if already_matched and not rematch_all:
            skipped_existing += 1
            continue

        await _upsert_match_for_record(
            db,
            record,
            parsed_jd,
            job_description_id=jd_row.id,
            include_llm=include_llm,
            candidate=candidate,
        )
        matched_new += 1

    if matched_new:
        await db.flush()
        await _recalculate_ranks(db, jd_row.id)
        await db.flush()

    response = await get_match_results(db, job_id=jd_row.id)
    response.matched_new = matched_new
    response.skipped_existing = skipped_existing
    return response


async def run_matching_for_resume(
    db: AsyncSession,
    resume_id: int,
    *,
    include_llm: bool = True,
    job_id: int | None = None,
) -> MatchResultDetail:
    jd_row, parsed_jd = await _require_parsed_jd(db, job_id)
    record = await db.get(ResumeRecord, resume_id)
    if not record:
        raise ValueError(f"Resume with id {resume_id} not found.")

    candidate = None
    if record.candidate_id:
        candidate = await db.get(Candidate, record.candidate_id)

    await _upsert_match_for_record(
        db,
        record,
        parsed_jd,
        job_description_id=jd_row.id,
        include_llm=include_llm,
        candidate=candidate,
    )
    await db.flush()
    await _recalculate_ranks(db, jd_row.id)
    await db.flush()

    detail = await get_match_for_resume(db, resume_id, job_id=jd_row.id)
    assert detail is not None
    return detail


def _match_to_detail(
    match: MatchResult, job_title: str | None = None
) -> MatchResultDetail:
    breakdown_items = build_component_breakdown(match.component_scores or {})
    subtotal = round(sum(item.weighted_points for item in breakdown_items), 2)
    return MatchResultDetail(
        resume_id=match.resume_id or 0,
        job_description_id=match.job_description_id,
        job_title=job_title,
        candidate_name=match.candidate_name,
        filename=match.filename,
        rank=match.rank,
        final_score=match.final_score,
        subtotal_score=subtotal,
        component_scores=match.component_scores,
        component_breakdown=[
            ComponentScoreBreakdown(
                key=item.key,
                label=item.label,
                weight_percent=item.weight_percent,
                score=item.score,
                weighted_points=item.weighted_points,
            )
            for item in breakdown_items
        ],
        matching_skills=match.matching_skills,
        missing_skills=match.missing_skills,
        red_flags=match.red_flags,
        red_flag_penalty=match.red_flag_penalty,
        strengths=match.strengths,
        weaknesses=match.weaknesses,
        summary=match.summary,
        matched_at=match.matched_at,
    )


async def get_match_results(
    db: AsyncSession, job_id: int | None = None
) -> MatchRunResponse:
    if job_id is None:
        jd_row = await get_active_job_row(db)
        job_id = jd_row.id
        job_title = jd_row.title
    else:
        jd_row = await db.get(JobDescription, job_id)
        if not jd_row:
            raise ValueError(f"Job description with id {job_id} not found.")
        job_title = jd_row.title

    result = await db.execute(
        select(MatchResult)
        .where(MatchResult.job_description_id == job_id)
        .order_by(MatchResult.rank.asc(), MatchResult.final_score.desc())
    )
    matches = result.scalars().all()
    display_title = _normalize_job_title(job_title)
    return MatchRunResponse(
        job_description_id=job_id,
        job_title=display_title,
        total=len(matches),
        results=[_match_to_detail(match, display_title) for match in matches],
    )


def _normalize_job_title(title: str | None) -> str | None:
    if not title:
        return None
    single = " ".join(title.split())
    return single[:80] if single else None


async def get_match_for_resume(
    db: AsyncSession, resume_id: int, job_id: int | None = None
) -> MatchResultDetail | None:
    if job_id is None:
        jd_row = await get_active_job_row(db)
        job_id = jd_row.id

    result = await db.execute(
        select(MatchResult).where(
            MatchResult.resume_id == resume_id,
            MatchResult.job_description_id == job_id,
        )
    )
    match = result.scalar_one_or_none()
    if not match:
        return None
    jd_row = await db.get(JobDescription, job_id)
    return _match_to_detail(match, _normalize_job_title(jd_row.title if jd_row else None))
