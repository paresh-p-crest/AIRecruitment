"""Pipeline snapshot for the recruitment dashboard."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from doc_converter import get_doc_extraction_capabilities
from extraction_chunked import CHUNK_THRESHOLD
from jd_service import get_active_job_row, get_job_description
from models import Candidate, JobDescription, MatchResult, ResumeRecord
from schemas import DashboardSnapshot, DashboardTopMatch

ARCHIVE_DIR = Path(__file__).resolve().parent / "Archive"


def _count_archive_doc_files() -> int | None:
    if not ARCHIVE_DIR.is_dir():
        return None
    count = 0
    for path in ARCHIVE_DIR.iterdir():
        if path.is_file() and path.suffix.lower() in {".doc", ".docx"}:
            count += 1
    return count


async def get_dashboard_snapshot(session: AsyncSession) -> DashboardSnapshot:
    total_candidates = (
        await session.scalar(select(func.count()).select_from(Candidate)) or 0
    )

    active_job = await get_active_job_row(session)

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

    top_rows = await session.execute(
        select(MatchResult)
        .where(MatchResult.job_description_id == active_job.id)
        .order_by(MatchResult.final_score.desc(), MatchResult.id.asc())
        .limit(5)
    )
    top_matches: list[DashboardTopMatch] = []
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

    jd = await get_job_description(session)
    job_count = (
        await session.scalar(select(func.count()).select_from(JobDescription)) or 0
    )

    return DashboardSnapshot(
        total_candidates=total_candidates,
        matched_candidates=matched_candidates,
        unmatched_candidates=unmatched_candidates,
        avg_match_score=round(avg_score, 1) if avg_score is not None else None,
        avg_years_experience=round(float(avg_years), 1) if avg_years is not None else None,
        job_description_valid=jd.is_valid_for_matching,
        job_description_has_content=jd.has_content,
        active_job_id=jd.id,
        active_job_title=jd.title,
        job_posting_count=job_count,
        file_types=file_types,
        top_matches=top_matches,
        doc_extraction_backends=get_doc_extraction_capabilities(),
        extraction_chunking_enabled=True,
        extraction_chunk_threshold=CHUNK_THRESHOLD,
        archive_doc_files=_count_archive_doc_files(),
    )
