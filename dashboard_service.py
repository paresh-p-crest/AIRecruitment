"""Pipeline snapshot for the recruitment dashboard."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from doc_converter import get_doc_extraction_capabilities
from extraction_chunked import CHUNK_THRESHOLD
from jd_service import find_active_job_row, get_job_description
from models import Candidate, JobDescription, MatchResult, ResumeRecord
from schemas import DashboardSkillStat, DashboardSnapshot, DashboardTopMatch

ARCHIVE_DIR = Path(__file__).resolve().parent / "Archive"

SKILL_PALETTE = (
    "#38bdf8",
    "#34d399",
    "#a78bfa",
    "#f472b6",
    "#fbbf24",
    "#fb7185",
    "#22d3ee",
    "#4ade80",
)

DISPLAY_SKILL_OVERRIDES = {
    "js": "JavaScript",
    "ts": "TypeScript",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "reactjs": "React",
    "react.js": "React",
    "vuejs": "Vue.js",
    "vue.js": "Vue.js",
    "dotnet": ".NET",
    ".net": ".NET",
    "c#": "C#",
    "c++": "C++",
}


def _count_archive_doc_files() -> int | None:
    if not ARCHIVE_DIR.is_dir():
        return None
    count = 0
    for path in ARCHIVE_DIR.iterdir():
        if path.is_file() and path.suffix.lower() in {".doc", ".docx"}:
            count += 1
    return count


def _normalize_skill_key(skill: str) -> str:
    return re.sub(r"\s+", " ", (skill or "").strip().lower())


def _display_skill_name(skill: str) -> str:
    key = _normalize_skill_key(skill)
    if not key:
        return ""
    if key in DISPLAY_SKILL_OVERRIDES:
        return DISPLAY_SKILL_OVERRIDES[key]
    if key.isupper() or (len(key) <= 4 and key.isalpha()):
        return skill.strip().upper()
    return skill.strip().title()


def _candidate_skill_keys(candidate: Candidate) -> set[str]:
    keys: set[str] = set()
    extracted = candidate.extracted_data or {}
    skills_block = extracted.get("Skills") or {}
    for bucket in ("Technical Skills", "technical_skills", "Soft Skills", "soft_skills"):
        for item in skills_block.get(bucket) or []:
            key = _normalize_skill_key(str(item))
            if key:
                keys.add(key)

    for entry in extracted.get("Professional_Experience") or []:
        for tech in entry.get("Technologies Used") or []:
            key = _normalize_skill_key(str(tech))
            if key:
                keys.add(key)

    return keys


def _build_top_skills(candidates: list[Candidate], limit: int = 8) -> list[DashboardSkillStat]:
    if not candidates:
        return []

    display_names: dict[str, str] = {}
    counts: Counter[str] = Counter()
    total = len(candidates)

    for candidate in candidates:
        for key in _candidate_skill_keys(candidate):
            counts[key] += 1
            if key not in display_names:
                display_names[key] = _display_skill_name(key)

    top = counts.most_common(limit)
    return [
        DashboardSkillStat(
            skill=display_names[key],
            candidate_count=count,
            percent=round((count / total) * 100, 1),
        )
        for key, count in top
        if display_names.get(key)
    ]


async def get_dashboard_snapshot(session: AsyncSession) -> DashboardSnapshot:
    total_candidates = (
        await session.scalar(select(func.count()).select_from(Candidate)) or 0
    )

    candidate_rows = await session.execute(select(Candidate))
    candidates = list(candidate_rows.scalars().all())
    top_skills = _build_top_skills(candidates)

    active_job = await find_active_job_row(session)
    has_active_job = active_job is not None

    matched_candidates = 0
    unmatched_candidates = total_candidates
    avg_score = None
    top_matches: list[DashboardTopMatch] = []
    active_job_id = None
    active_job_title = None
    job_description_valid = False
    job_description_has_content = False

    if active_job:
        active_job_id = active_job.id
        active_job_title = active_job.title

        matched_candidates = (
            await session.scalar(
                select(func.count())
                .select_from(MatchResult)
                .where(MatchResult.job_description_id == active_job.id)
            )
            or 0
        )
        unmatched_candidates = max(0, total_candidates - matched_candidates)

        avg_score = await session.scalar(
            select(func.avg(MatchResult.final_score)).where(
                MatchResult.job_description_id == active_job.id
            )
        )

        top_rows = await session.execute(
            select(MatchResult)
            .where(MatchResult.job_description_id == active_job.id)
            .order_by(MatchResult.final_score.desc(), MatchResult.id.asc())
            .limit(5)
        )
        for match in top_rows.scalars().all():
            top_matches.append(
                DashboardTopMatch(
                    resume_id=match.resume_id or 0,
                    candidate_name=match.candidate_name,
                    filename=match.filename,
                    final_score=round(match.final_score, 1),
                    rank=match.rank,
                )
            )

        jd = await get_job_description(session, active_job.id)
        job_description_valid = jd.is_valid_for_matching
        job_description_has_content = jd.has_content
    else:
        jd = None

    metrics_rows = await session.execute(select(Candidate.calculated_metrics))
    year_values: list[float] = []
    for (metrics,) in metrics_rows.all():
        if not metrics:
            continue
        raw_years = metrics.get("Total_Years_Of_Experience")
        if raw_years is not None:
            try:
                year_values.append(float(raw_years))
            except (TypeError, ValueError):
                continue
    avg_years = sum(year_values) / len(year_values) if year_values else None

    file_rows = await session.execute(
        select(ResumeRecord.filename).where(ResumeRecord.is_default.is_(True))
    )
    file_types: dict[str, int] = {"pdf": 0, "doc": 0, "docx": 0, "other": 0}
    for (filename,) in file_rows.all():
        ext = Path(filename or "").suffix.lower().lstrip(".")
        if ext in file_types:
            file_types[ext] += 1
        else:
            file_types["other"] += 1

    job_count = (
        await session.scalar(select(func.count()).select_from(JobDescription)) or 0
    )

    return DashboardSnapshot(
        total_candidates=total_candidates,
        matched_candidates=matched_candidates,
        unmatched_candidates=unmatched_candidates,
        avg_match_score=round(avg_score, 1) if avg_score is not None else None,
        avg_years_experience=round(float(avg_years), 1) if avg_years is not None else None,
        has_active_job=has_active_job,
        job_description_valid=job_description_valid,
        job_description_has_content=job_description_has_content,
        active_job_id=active_job_id,
        active_job_title=active_job_title,
        job_posting_count=job_count,
        file_types=file_types,
        top_matches=top_matches,
        top_skills=top_skills,
        doc_extraction_backends=get_doc_extraction_capabilities(),
        extraction_chunking_enabled=True,
        extraction_chunk_threshold=CHUNK_THRESHOLD,
        archive_doc_files=_count_archive_doc_files(),
    )
