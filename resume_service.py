"""Resume upload processing with duplicate detection."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from contact_extract import normalize_email  # re-exported for callers
from graph import run_extraction_pipeline
from models import ResumeRecord
from schemas import ResumeUploadResponse
from utils import extract_text_from_bytes, validate_resume_bytes

logger = logging.getLogger(__name__)

MAX_BULK_FILES = 50
SkipReason = Literal["duplicate_file", "duplicate_email"]
ResultStatus = Literal["success", "skipped", "error"]


@dataclass
class ProcessResumeResult:
    filename: str
    status: ResultStatus
    message: str | None = None
    resume: ResumeRecord | None = None
    duplicate_of_id: int | None = None
    skip_reason: SkipReason | None = None


def compute_file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def record_to_response(record: ResumeRecord) -> ResumeUploadResponse:
    return ResumeUploadResponse(
        id=record.id,
        filename=record.filename,
        raw_text=record.raw_text,
        extracted_data=record.extracted_data,
        calculated_metrics=record.calculated_metrics,
        created_at=record.created_at,
    )


async def find_by_file_hash(db: AsyncSession, file_hash: str) -> ResumeRecord | None:
    result = await db.execute(
        select(ResumeRecord).where(ResumeRecord.file_hash == file_hash).limit(1)
    )
    return result.scalar_one_or_none()


async def find_by_candidate_email(
    db: AsyncSession, email: str
) -> ResumeRecord | None:
    result = await db.execute(
        select(ResumeRecord)
        .where(ResumeRecord.candidate_email == email)
        .order_by(ResumeRecord.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def process_resume_bytes(
    db: AsyncSession,
    filename: str,
    content: bytes,
    *,
    seen_hashes: set[str] | None = None,
    seen_emails: set[str] | None = None,
) -> ProcessResumeResult:
    """Parse, extract, and persist one resume; skip known duplicates."""
    safe_filename = filename or "unknown"

    try:
        validate_resume_bytes(safe_filename, content)
    except ValueError as exc:
        return ProcessResumeResult(
            filename=safe_filename,
            status="error",
            message=str(exc),
        )

    file_hash = compute_file_hash(content)

    if seen_hashes is not None and file_hash in seen_hashes:
        return ProcessResumeResult(
            filename=safe_filename,
            status="skipped",
            skip_reason="duplicate_file",
            message="Duplicate file in this upload batch (same content as another selected file).",
        )

    existing_file = await find_by_file_hash(db, file_hash)
    if existing_file:
        return ProcessResumeResult(
            filename=safe_filename,
            status="skipped",
            skip_reason="duplicate_file",
            message=f"Resume already uploaded as '{existing_file.filename}'.",
            duplicate_of_id=existing_file.id,
        )

    try:
        raw_text = extract_text_from_bytes(safe_filename, content)
    except ValueError as exc:
        return ProcessResumeResult(
            filename=safe_filename,
            status="error",
            message=str(exc),
        )

    try:
        pipeline_result = await run_extraction_pipeline(raw_text, db)
    except ValueError as exc:
        return ProcessResumeResult(
            filename=safe_filename,
            status="error",
            message=str(exc),
        )
    except Exception as exc:
        logger.exception("Extraction failed for %s", safe_filename)
        return ProcessResumeResult(
            filename=safe_filename,
            status="error",
            message=f"Extraction pipeline failed: {exc}",
        )

    parsed = pipeline_result.get("parsed_json")
    metrics = pipeline_result.get("calculated_metrics")
    if not parsed or not metrics:
        return ProcessResumeResult(
            filename=safe_filename,
            status="error",
            message="Extraction pipeline did not return complete results.",
        )

    extracted_data = parsed.model_dump(by_alias=True)
    calculated_metrics = metrics.model_dump(by_alias=True)
    personal_info = extracted_data.get("Personal_Info", {})
    candidate_email = normalize_email(personal_info.get("Email"))

    if candidate_email:
        if seen_emails is not None and candidate_email in seen_emails:
            return ProcessResumeResult(
                filename=safe_filename,
                status="skipped",
                skip_reason="duplicate_email",
                message=(
                    "Duplicate candidate in this upload batch "
                    f"(email: {candidate_email})."
                ),
            )

        existing_email = await find_by_candidate_email(db, candidate_email)
        if existing_email:
            return ProcessResumeResult(
                filename=safe_filename,
                status="skipped",
                skip_reason="duplicate_email",
                message=(
                    f"Candidate already exists (email: {candidate_email}) "
                    f"from '{existing_email.filename}'."
                ),
                duplicate_of_id=existing_email.id,
            )

    record = ResumeRecord(
        filename=safe_filename,
        raw_text=raw_text,
        extracted_data=extracted_data,
        calculated_metrics=calculated_metrics,
        file_hash=file_hash,
        candidate_email=candidate_email,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)

    if seen_hashes is not None:
        seen_hashes.add(file_hash)
    if seen_emails is not None and candidate_email:
        seen_emails.add(candidate_email)

    return ProcessResumeResult(
        filename=safe_filename,
        status="success",
        resume=record,
    )
