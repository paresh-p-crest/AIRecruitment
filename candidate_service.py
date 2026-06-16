"""Candidate-centric upload, duplicate handling, and hybrid extraction orchestration."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from graph import run_extraction_pipeline
from models import Candidate, DuplicateCheckSettings, ResumeRecord, UploadBatch, UploadBatchItem
from contact_extract import (
    extract_emails_from_text,
    extract_linkedin_urls_from_text,
    extract_phones_from_text,
    normalize_email,
)
from prescan_service import prescan_batch
from resume_header import (
    extract_name_from_text_header,
    extract_skills_from_text_section,
    extract_title_from_text_header,
    extract_years_hint_from_text,
    parse_name_title_from_filename,
)
from resume_service import compute_file_hash
from textract_service import extract_text_with_textract

logger = logging.getLogger(__name__)

DuplicatePolicy = Literal["ignore", "add_as_default", "add_as_new_resume"]
ProcessStatus = Literal["success", "ignored", "error", "duplicate_review"]


def split_name(full_name: str | None) -> tuple[str | None, str | None]:
    if not full_name or not full_name.strip():
        return None, None
    parts = full_name.strip().split()
    if len(parts) == 1:
        return parts[0], None
    return parts[0], " ".join(parts[1:])


def identity_from_extracted(extracted_data: dict[str, Any]) -> dict[str, Any]:
    personal = extracted_data.get("Personal_Info", {}) or {}
    full_name = personal.get("Name")
    first, last = split_name(full_name)
    return {
        "first_name": first,
        "last_name": last,
        "email": normalize_email(personal.get("Email")),
        "phone": (personal.get("Phone") or "").strip() or None,
        "linkedin_url": None,
        "current_location": personal.get("Location"),
        "country": None,
        "title": personal.get("Current Designation"),
    }


def enrich_extracted_from_raw_text(
    extracted_data: dict[str, Any],
    identity: dict[str, Any],
    raw_text: str,
    *,
    filename: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Backfill contact fields from parsed resume text when the LLM omitted them.

    Pre-scan already finds emails via regex; this keeps AI extraction and saved
    profiles consistent when the model misses header contact details.
    """
    if not raw_text:
        return extracted_data, identity

    personal = dict(extracted_data.get("Personal_Info") or {})

    if not normalize_email(identity.get("email")):
        identity["email"] = None
        emails = extract_emails_from_text(raw_text)
        if emails:
            email = normalize_email(emails[0])
            identity["email"] = email
            personal["Email"] = email
            logger.info("Backfilled email from raw resume text: %s", email)

    if not identity.get("phone"):
        phones = extract_phones_from_text(raw_text)
        if phones:
            identity["phone"] = phones[0]
            if not personal.get("Phone"):
                personal["Phone"] = phones[0]

    if not identity.get("linkedin_url"):
        linkedin_urls = extract_linkedin_urls_from_text(raw_text)
        if linkedin_urls:
            identity["linkedin_url"] = linkedin_urls[0]

    if not identity.get("first_name") and personal.get("Name"):
        first, last = split_name(personal.get("Name"))
        identity["first_name"] = first
        identity["last_name"] = last

    if not personal.get("Name") and identity.get("first_name"):
        name = " ".join(
            p for p in (identity.get("first_name"), identity.get("last_name")) if p
        )
        if name:
            personal["Name"] = name

    if not identity.get("first_name"):
        header_name = extract_name_from_text_header(raw_text)
        file_name, file_title = parse_name_title_from_filename(filename or "")
        full_name = header_name or file_name
        if full_name:
            first, last = split_name(full_name)
            identity["first_name"] = first
            identity["last_name"] = last
            personal["Name"] = full_name
            logger.info("Backfilled name from resume header/filename: %s", full_name)

    if not identity.get("title"):
        title = extract_title_from_text_header(
            raw_text, personal.get("Name") or identity.get("first_name")
        )
        if not title and filename:
            _, title = parse_name_title_from_filename(filename)
        if title:
            identity["title"] = title
            personal["Current Designation"] = title
            logger.info("Backfilled title from resume header/filename: %s", title)

    skills_block = dict(extracted_data.get("Skills") or {})
    tech = list(skills_block.get("Technical Skills") or skills_block.get("technical_skills") or [])
    soft = list(skills_block.get("Soft Skills") or skills_block.get("soft_skills") or [])
    if not tech:
        fallback_skills = extract_skills_from_text_section(raw_text)
        if fallback_skills:
            tech = fallback_skills
            logger.info("Backfilled %d skills from resume text section", len(tech))
    if tech or soft:
        extracted_data = {
            **extracted_data,
            "Skills": {"Technical Skills": tech, "Soft Skills": soft},
        }

    updated = {**extracted_data, "Personal_Info": personal}
    return updated, identity


def enrich_calculated_metrics_from_text(
    calculated_metrics: dict[str, Any],
    raw_text: str,
) -> dict[str, Any]:
    """Fill experience years from summary text when LLM returned zero/empty."""
    metrics = dict(calculated_metrics or {})
    current = metrics.get("Total_Years_Of_Experience")
    if current not in (None, "", 0, 0.0):
        return metrics

    years = extract_years_hint_from_text(raw_text)
    if years is not None:
        metrics["Total_Years_Of_Experience"] = years
        logger.info("Backfilled years of experience from resume text: %s", years)
    return metrics


async def ensure_duplicate_settings(db: AsyncSession) -> DuplicateCheckSettings:
    result = await db.execute(
        select(DuplicateCheckSettings).where(DuplicateCheckSettings.id == 1)
    )
    row = result.scalar_one_or_none()
    if row:
        return row
    row = DuplicateCheckSettings(id=1)
    db.add(row)
    await db.flush()
    return row


def _normalize_phone_digits(phone: str | None) -> str | None:
    if not phone:
        return None
    import re

    digits = re.sub(r"\D", "", phone)
    return digits if len(digits) >= 10 else None


async def get_existing_hashes_and_emails(
    db: AsyncSession,
) -> tuple[set[str], set[str], set[str], set[str]]:
    hash_result = await db.execute(
        select(ResumeRecord.file_hash).where(ResumeRecord.file_hash.is_not(None))
    )
    email_result = await db.execute(select(Candidate.email))
    phone_result = await db.execute(
        select(Candidate.phone).where(Candidate.phone.is_not(None))
    )
    linkedin_result = await db.execute(
        select(Candidate.linkedin_url).where(Candidate.linkedin_url.is_not(None))
    )
    orphan_email_result = await db.execute(
        select(ResumeRecord.candidate_email).where(
            ResumeRecord.candidate_email.is_not(None),
            ResumeRecord.candidate_id.is_(None),
        )
    )
    hashes = {row[0] for row in hash_result if row[0]}
    emails: set[str] = set()
    phones: set[str] = set()
    linkedin_urls: set[str] = set()
    for row in email_result:
        if row[0]:
            emails.add(row[0].lower())
    for row in phone_result:
        normalized = _normalize_phone_digits(row[0])
        if normalized:
            phones.add(normalized)
    for row in orphan_email_result:
        normalized = normalize_email(row[0])
        if normalized:
            emails.add(normalized)
    for row in linkedin_result:
        if row[0]:
            linkedin_urls.add(row[0].strip().lower())
    return hashes, emails, phones, linkedin_urls


async def find_candidate_by_identity(
    db: AsyncSession, identity: dict[str, Any], settings: DuplicateCheckSettings
) -> Candidate | None:
    fields = settings.primary_fields or ["email", "phone", "linkedin_url"]

    email = identity.get("email")
    if "email" in fields and email:
        result = await db.execute(select(Candidate).where(Candidate.email == email))
        found = result.scalar_one_or_none()
        if found:
            return found

    phone = identity.get("phone")
    if "phone" in fields and phone:
        other = await _find_candidate_by_phone(db, phone)
        if other:
            return other

    linkedin = (identity.get("linkedin_url") or "").strip()
    if "linkedin_url" in fields and linkedin:
        result = await db.execute(
            select(Candidate).where(Candidate.linkedin_url == linkedin)
        )
        found = result.scalar_one_or_none()
        if found:
            return found

    for field in ("first_name", "last_name", "current_location", "country", "title"):
        if field not in fields:
            continue
        value = (identity.get(field) or "").strip()
        if not value:
            continue
        column = getattr(Candidate, field)
        result = await db.execute(select(Candidate).where(column == value))
        found = result.scalar_one_or_none()
        if found:
            return found

    return None


def apply_profile_to_candidate(
    candidate: Candidate,
    extracted_data: dict,
    metrics: dict,
    *,
    identity: dict[str, Any] | None = None,
) -> None:
    identity = identity or identity_from_extracted(extracted_data)
    candidate.first_name = identity.get("first_name")
    candidate.last_name = identity.get("last_name")
    if identity.get("email"):
        candidate.email = identity["email"]
    candidate.phone = identity.get("phone") or candidate.phone
    candidate.linkedin_url = identity.get("linkedin_url") or candidate.linkedin_url
    candidate.current_location = identity.get("current_location") or candidate.current_location
    candidate.country = identity.get("country") or candidate.country
    candidate.title = identity.get("title") or candidate.title
    candidate.extracted_data = extracted_data
    candidate.calculated_metrics = metrics
    candidate.updated_at = datetime.now(timezone.utc)


async def set_default_resume(
    db: AsyncSession, candidate: Candidate, resume: ResumeRecord
) -> None:
    result = await db.execute(
        select(ResumeRecord).where(ResumeRecord.candidate_id == candidate.id)
    )
    for existing in result.scalars().all():
        existing.is_default = False
    resume.is_default = True
    resume.candidate_id = candidate.id
    if candidate.extracted_data:
        resume.extracted_data = candidate.extracted_data
        resume.calculated_metrics = candidate.calculated_metrics


def _apply_extraction_metrics(
    outcome: dict[str, Any],
    duration_ms: int,
    usage: Any | None,
    *,
    llm_model: str | None = None,
    cost: dict[str, float | None] | None = None,
) -> dict[str, Any]:
    outcome["duration_ms"] = duration_ms
    outcome["llm_model"] = llm_model
    if usage is not None and getattr(usage, "has_usage", False):
        outcome["input_tokens"] = usage.input_tokens
        outcome["output_tokens"] = usage.output_tokens
        outcome["total_tokens"] = usage.total_tokens
    else:
        outcome["input_tokens"] = None
        outcome["output_tokens"] = None
        outcome["total_tokens"] = None
    if cost:
        outcome["estimated_cost_usd"] = cost.get("estimated_cost_usd")
        outcome["estimated_cost_credits"] = cost.get("estimated_cost_credits")
    else:
        outcome["estimated_cost_usd"] = None
        outcome["estimated_cost_credits"] = None
    return outcome


async def _enrich_outcome_metrics(
    db: AsyncSession, outcome: dict[str, Any], duration_ms: int, usage: Any | None
) -> dict[str, Any]:
    from model_pricing_service import compute_upload_cost
    from settings_service import get_active_model_name, get_effective_settings

    settings = await get_effective_settings(db)
    model = get_active_model_name(settings)
    inp = outcome.get("input_tokens")
    out = outcome.get("output_tokens")
    total = outcome.get("total_tokens")
    if usage is not None and getattr(usage, "has_usage", False):
        inp = usage.input_tokens
        out = usage.output_tokens
        total = usage.total_tokens
    cost = await compute_upload_cost(db, model, inp, out, total)
    return _apply_extraction_metrics(
        outcome, duration_ms, usage, llm_model=model, cost=cost
    )


async def hybrid_extract(
    filename: str, content: bytes, db: AsyncSession
) -> tuple[str, str, dict, dict, int, Any | None]:
    from llm_usage import get_usage

    started = time.perf_counter()
    raw_text, source = extract_text_with_textract(content, filename)
    pipeline_result = await run_extraction_pipeline(raw_text, db)
    duration_ms = int((time.perf_counter() - started) * 1000)
    usage = get_usage()
    parsed = pipeline_result.get("parsed_json")
    metrics = pipeline_result.get("calculated_metrics")
    if not parsed or not metrics:
        raise ValueError("Extraction pipeline did not return complete results.")
    extracted_data = parsed.model_dump(by_alias=True)
    calculated_metrics = metrics.model_dump(by_alias=True)
    return raw_text, source, extracted_data, calculated_metrics, duration_ms, usage


async def _record_single_upload_history(
    db: AsyncSession,
    filename: str,
    content: bytes,
    outcome: dict[str, Any],
) -> None:
    status = outcome.get("status", "error")
    succeeded = 1 if status == "success" else 0
    ignored = 1 if status == "ignored" else 0
    failed = 1 if status in {"error", "duplicate_review"} else 0

    batch = UploadBatch(
        mode="single",
        status="completed",
        total_files=1,
        processed=1,
        succeeded=succeeded,
        ignored=ignored,
        failed=failed,
    )
    db.add(batch)
    await db.flush()

    item = UploadBatchItem(
        batch_id=batch.id,
        filename=filename,
        file_hash=compute_file_hash(content),
        scan_status="ok",
        process_status=status,
        message=outcome.get("message"),
        candidate_id=outcome.get("candidate_id"),
        resume_id=outcome.get("resume_id"),
        duration_ms=outcome.get("duration_ms"),
        input_tokens=outcome.get("input_tokens"),
        output_tokens=outcome.get("output_tokens"),
        total_tokens=outcome.get("total_tokens"),
        llm_model=outcome.get("llm_model"),
        estimated_cost_usd=outcome.get("estimated_cost_usd"),
        estimated_cost_credits=outcome.get("estimated_cost_credits"),
    )
    db.add(item)


async def list_upload_history(db: AsyncSession, limit: int = 50) -> list[dict[str, Any]]:
    result = await db.execute(
        select(UploadBatchItem, UploadBatch)
        .join(UploadBatch, UploadBatchItem.batch_id == UploadBatch.id)
        .order_by(UploadBatchItem.id.desc())
        .limit(limit)
    )
    rows = result.all()
    history: list[dict[str, Any]] = []
    for item, batch in rows:
        history.append(
            {
                "id": item.id,
                "batch_id": batch.id,
                "mode": batch.mode,
                "filename": item.filename,
                "process_status": item.process_status,
                "message": item.message,
                "candidate_id": item.candidate_id,
                "resume_id": item.resume_id,
                "duration_ms": item.duration_ms,
                "input_tokens": item.input_tokens,
                "output_tokens": item.output_tokens,
                "total_tokens": item.total_tokens,
                "llm_model": item.llm_model,
                "estimated_cost_usd": item.estimated_cost_usd,
                "estimated_cost_credits": item.estimated_cost_credits,
                "created_at": batch.created_at,
            }
        )
    return history


async def delete_upload_history_item(db: AsyncSession, item_id: int) -> None:
    item = await db.get(UploadBatchItem, item_id)
    if not item:
        raise ValueError(f"Upload history item {item_id} not found.")

    batch_id = item.batch_id
    await db.delete(item)
    await db.flush()

    remaining = await db.scalar(
        select(func.count())
        .select_from(UploadBatchItem)
        .where(UploadBatchItem.batch_id == batch_id)
    )
    if not remaining:
        batch = await db.get(UploadBatch, batch_id)
        if batch:
            await db.delete(batch)


async def clear_upload_history(db: AsyncSession) -> int:
    count = await db.scalar(select(func.count()).select_from(UploadBatchItem)) or 0
    await db.execute(delete(UploadBatchItem))
    await db.execute(delete(UploadBatch))
    return count


async def process_uploaded_file(
    db: AsyncSession,
    filename: str,
    content: bytes,
    *,
    duplicate_policy: DuplicatePolicy | None = None,
    allow_duplicate_review: bool = False,
    record_history: bool = True,
) -> dict[str, Any]:
    """Full hybrid pipeline for one file after pre-scan gate passed."""
    file_hash = compute_file_hash(content)
    settings = await ensure_duplicate_settings(db)
    duration_ms = 0
    usage = None

    try:
        (
            raw_text,
            source,
            extracted_data,
            calculated_metrics,
            duration_ms,
            usage,
        ) = await hybrid_extract(filename, content, db)
    except Exception as exc:
        outcome = {
            "status": "error",
            "filename": filename,
            "message": str(exc),
            "duration_ms": duration_ms,
        }
        outcome = await _enrich_outcome_metrics(db, outcome, duration_ms, usage)
        if record_history:
            await _record_single_upload_history(db, filename, content, outcome)
        return outcome
    identity = identity_from_extracted(extracted_data)
    extracted_data, identity = enrich_extracted_from_raw_text(
        extracted_data, identity, raw_text, filename=filename
    )
    calculated_metrics = enrich_calculated_metrics_from_text(calculated_metrics, raw_text)
    email = normalize_email(identity.get("email"))
    if not email:
        personal_info = extracted_data.get("Personal_Info") or {}
        email = normalize_email(personal_info.get("Email"))
    if email:
        identity["email"] = email
        personal = dict(extracted_data.get("Personal_Info") or {})
        personal["Email"] = email
        extracted_data = {**extracted_data, "Personal_Info": personal}
    if not email:
        outcome = {
            "status": "error",
            "filename": filename,
            "message": "No email found after AI extraction. Candidate not saved.",
        }
        outcome = await _enrich_outcome_metrics(db, outcome, duration_ms, usage)
        if record_history:
            await _record_single_upload_history(db, filename, content, outcome)
        return outcome

    existing = await find_candidate_by_identity(db, identity, settings)

    if existing and allow_duplicate_review and duplicate_policy is None:
        outcome = {
            "status": "duplicate_review",
            "filename": filename,
            "message": "Duplicate candidate found.",
            "existing_candidate_id": existing.id,
            "parsed_preview": {
                "identity": identity,
                "extracted_data": extracted_data,
                "calculated_metrics": calculated_metrics,
            },
            "existing_snapshot": {
                "candidate_id": existing.id,
                "first_name": existing.first_name,
                "last_name": existing.last_name,
                "email": existing.email,
                "phone": existing.phone,
                "linkedin_url": existing.linkedin_url,
                "current_location": existing.current_location,
                "country": existing.country,
                "title": existing.title,
                "extracted_data": existing.extracted_data,
                "calculated_metrics": existing.calculated_metrics,
            },
        }
        outcome = await _enrich_outcome_metrics(db, outcome, duration_ms, usage)
        return outcome

    policy = duplicate_policy or "add_as_default"

    if existing and policy == "ignore":
        outcome = {
            "status": "ignored",
            "filename": filename,
            "message": f"Duplicate ignored for existing candidate ({existing.email}).",
            "candidate_id": existing.id,
        }
        outcome = await _enrich_outcome_metrics(db, outcome, duration_ms, usage)
        if record_history:
            await _record_single_upload_history(db, filename, content, outcome)
        return outcome

    if existing:
        candidate = existing
        apply_profile_to_candidate(
            candidate, extracted_data, calculated_metrics, identity=identity
        )
        is_default = policy == "add_as_default"
    else:
        candidate = Candidate(
            email=email,
            extracted_data=extracted_data,
            calculated_metrics=calculated_metrics,
        )
        apply_profile_to_candidate(
            candidate, extracted_data, calculated_metrics, identity=identity
        )
        db.add(candidate)
        await db.flush()
        is_default = True

    resume = ResumeRecord(
        candidate_id=candidate.id,
        filename=filename,
        file_hash=file_hash,
        raw_text=raw_text,
        extraction_source=source,
        is_default=is_default,
        candidate_email=email,
        extracted_data=extracted_data,
        calculated_metrics=calculated_metrics,
    )
    db.add(resume)
    await db.flush()

    if is_default:
        await set_default_resume(db, candidate, resume)

    await db.refresh(candidate)
    await db.refresh(resume)

    outcome = {
        "status": "success",
        "filename": filename,
        "message": "Candidate processed successfully.",
        "candidate_id": candidate.id,
        "resume_id": resume.id,
        "is_default": resume.is_default,
        "extraction_source": source,
    }
    outcome = await _enrich_outcome_metrics(db, outcome, duration_ms, usage)
    if record_history:
        await _record_single_upload_history(db, filename, content, outcome)
    return outcome


async def run_prescan(db: AsyncSession, files: list[tuple[str, bytes]]) -> dict:
    hashes, emails, phones, linkedin_urls = await get_existing_hashes_and_emails(db)
    report = prescan_batch(
        files,
        existing_hashes=hashes,
        existing_emails=emails,
        existing_phones=phones,
        existing_linkedin_urls=linkedin_urls,
    )
    blocked = sum(1 for r in report.results if not r.processable)
    est_tokens_per_resume = 4500
    return {
        "total": report.total,
        "ready": report.ready,
        "warnings": report.warnings,
        "errors": report.errors,
        "can_proceed": report.can_proceed,
        "ai_calls_avoided": blocked,
        "estimated_tokens_saved": blocked * est_tokens_per_resume,
        "results": [
            {
                "filename": r.filename,
                "file_hash": r.file_hash,
                "status": r.status,
                "emails_found": r.emails_found,
                "phones_found": r.phones_found,
                "linkedin_urls_found": r.linkedin_urls_found,
                "message": r.message,
                "duplicate_of_filename": r.duplicate_of_filename,
                "duplicate_in_database": r.duplicate_in_database,
                "skipped_ai": r.skipped_ai,
                "processable": r.processable,
            }
            for r in report.results
        ],
    }


async def run_bulk_process(
    db: AsyncSession,
    files: list[tuple[str, bytes]],
    duplicate_policy: DuplicatePolicy,
) -> dict:
    batch = UploadBatch(
        mode="bulk",
        duplicate_policy=duplicate_policy,
        status="processing",
        total_files=len(files),
    )
    db.add(batch)
    await db.flush()

    results = []
    succeeded = ignored = failed = 0

    for filename, content in files:
        item = UploadBatchItem(
            batch_id=batch.id,
            filename=filename,
            file_hash=compute_file_hash(content),
            scan_status="ok",
            process_status="processing",
        )
        db.add(item)
        await db.flush()

        try:
            outcome = await process_uploaded_file(
                db,
                filename,
                content,
                duplicate_policy=duplicate_policy,
                allow_duplicate_review=False,
                record_history=False,
            )
        except Exception as exc:
            outcome = {
                "status": "error",
                "filename": filename,
                "message": str(exc),
            }

        item.process_status = outcome["status"]
        item.message = outcome.get("message")
        item.candidate_id = outcome.get("candidate_id")
        item.resume_id = outcome.get("resume_id")
        item.duration_ms = outcome.get("duration_ms")
        item.input_tokens = outcome.get("input_tokens")
        item.output_tokens = outcome.get("output_tokens")
        item.total_tokens = outcome.get("total_tokens")
        item.llm_model = outcome.get("llm_model")
        item.estimated_cost_usd = outcome.get("estimated_cost_usd")
        item.estimated_cost_credits = outcome.get("estimated_cost_credits")

        if outcome["status"] == "success":
            succeeded += 1
        elif outcome["status"] == "ignored":
            ignored += 1
        else:
            failed += 1

        results.append(outcome)

    batch.status = "completed"
    batch.processed = len(files)
    batch.succeeded = succeeded
    batch.failed = failed
    batch.ignored = ignored

    return {
        "batch_id": batch.id,
        "total": len(files),
        "succeeded": succeeded,
        "ignored": ignored,
        "failed": failed,
        "results": results,
    }


async def confirm_single_upload(
    db: AsyncSession,
    filename: str,
    content: bytes,
    duplicate_policy: DuplicatePolicy,
) -> dict:
    return await process_uploaded_file(
        db,
        filename,
        content,
        duplicate_policy=duplicate_policy,
        allow_duplicate_review=False,
    )


def _candidate_display_name(candidate: Candidate) -> str | None:
    parts = [candidate.first_name, candidate.last_name]
    name = " ".join(p for p in parts if p)
    if name:
        return name
    return (candidate.extracted_data or {}).get("Personal_Info", {}).get("Name")


async def list_candidates(db: AsyncSession, job_id: int | None = None) -> list[dict]:
    from jd_service import get_active_job_row
    from models import JobDescription, MatchResult

    if job_id is None:
        scope_job = await get_active_job_row(db)
    else:
        scope_job = await db.get(JobDescription, job_id)
        if not scope_job:
            raise ValueError(f"Job description with id {job_id} not found.")

    result = await db.execute(
        select(Candidate)
        .options(selectinload(Candidate.resumes))
        .order_by(Candidate.updated_at.desc())
    )
    candidates = result.scalars().unique().all()

    match_result = await db.execute(
        select(MatchResult).where(MatchResult.job_description_id == scope_job.id)
    )
    matches_by_candidate = {
        m.candidate_id: m for m in match_result.scalars().all() if m.candidate_id
    }

    items = []
    for candidate in candidates:
        default_resume = next(
            (r for r in candidate.resumes if r.is_default),
            candidate.resumes[0] if candidate.resumes else None,
        )
        metrics = candidate.calculated_metrics or {}
        match = matches_by_candidate.get(candidate.id)
        items.append(
            {
                "id": candidate.id,
                "first_name": candidate.first_name,
                "last_name": candidate.last_name,
                "email": candidate.email,
                "phone": candidate.phone,
                "title": candidate.title,
                "total_years_of_experience": metrics.get("Total_Years_Of_Experience"),
                "default_resume_id": default_resume.id if default_resume else None,
                "default_resume_filename": default_resume.filename if default_resume else None,
                "resume_count": len(candidate.resumes),
                "match_score": match.final_score if match else None,
                "match_rank": match.rank if match else None,
                "created_at": candidate.created_at,
                "updated_at": candidate.updated_at,
            }
        )
    return items


def _sync_extracted_personal_info(candidate: Candidate) -> None:
    """Keep JSON profile in sync with editable identity columns."""
    data = dict(candidate.extracted_data or {})
    personal = dict(data.get("Personal_Info") or {})
    name = " ".join(p for p in (candidate.first_name, candidate.last_name) if p)
    if name:
        personal["Name"] = name
    if candidate.email:
        personal["Email"] = candidate.email
    if candidate.phone:
        personal["Phone"] = candidate.phone
    if candidate.current_location:
        personal["Location"] = candidate.current_location
    if candidate.title:
        personal["Current Designation"] = candidate.title
    data["Personal_Info"] = personal
    candidate.extracted_data = data


def _phones_for_candidate(candidate: Candidate) -> list[str]:
    """Collect phone values from the profile column and extracted resume data."""
    phones: list[str] = []
    if candidate.phone:
        phones.append(candidate.phone)
    personal = (candidate.extracted_data or {}).get("Personal_Info", {}) or {}
    extracted_phone = personal.get("Phone")
    if extracted_phone:
        phones.append(str(extracted_phone))
    return phones


async def _find_candidate_by_phone(
    db: AsyncSession, phone: str, exclude_id: int | None = None
) -> Candidate | None:
    target = _normalize_phone_digits(phone)
    if not target:
        return None
    query = select(Candidate)
    if exclude_id is not None:
        query = query.where(Candidate.id != exclude_id)
    result = await db.execute(query)
    for row in result.scalars():
        for candidate_phone in _phones_for_candidate(row):
            if _normalize_phone_digits(candidate_phone) == target:
                return row
    return None


async def _find_candidate_by_email(
    db: AsyncSession, email: str, exclude_id: int | None = None
) -> Candidate | None:
    normalized = normalize_email(email)
    if not normalized:
        return None
    query = select(Candidate)
    if exclude_id is not None:
        query = query.where(Candidate.id != exclude_id)
    result = await db.execute(query)
    for row in result.scalars():
        if normalize_email(row.email) == normalized:
            return row
        personal = (row.extracted_data or {}).get("Personal_Info", {}) or {}
        if normalize_email(personal.get("Email")) == normalized:
            return row
    return None


async def find_profile_duplicate_warnings(
    db: AsyncSession,
    candidate_id: int,
    *,
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    linkedin_url: str | None = None,
    current_location: str | None = None,
    country: str | None = None,
    title: str | None = None,
    passport_number: str | None = None,
) -> list[dict[str, Any]]:
    """Return duplicate warnings for editable identity fields (warn on save, not block)."""
    settings = await ensure_duplicate_settings(db)
    warn_fields = set(settings.primary_fields or []) | set(settings.secondary_fields or [])

    warnings: list[dict[str, Any]] = []

    def add_warning(field: str, label: str, other: Candidate, detail: str) -> None:
        if any(w["field"] == field for w in warnings):
            return
        warnings.append(
            {
                "field": field,
                "label": label,
                "message": detail,
                "conflicting_candidate_id": other.id,
                "conflicting_candidate_name": _candidate_display_name(other),
                "conflicting_candidate_email": other.email,
            }
        )

    if "email" in warn_fields and email:
        other = await _find_candidate_by_email(db, email, candidate_id)
        if other:
            normalized = normalize_email(email)
            add_warning(
                "email",
                "Email",
                other,
                f"Email '{normalized}' already belongs to another candidate.",
            )

    if "phone" in warn_fields and phone:
        other = await _find_candidate_by_phone(db, phone, candidate_id)
        if other:
            add_warning(
                "phone",
                "Phone",
                other,
                f"Phone number matches another candidate ({phone.strip()}).",
            )

    if "linkedin_url" in warn_fields and linkedin_url and linkedin_url.strip():
        url = linkedin_url.strip()
        result = await db.execute(
            select(Candidate).where(
                Candidate.linkedin_url == url,
                Candidate.id != candidate_id,
            )
        )
        other = result.scalar_one_or_none()
        if other:
            add_warning("linkedin_url", "LinkedIn", other, "LinkedIn URL matches another candidate.")

    if "passport_number" in warn_fields and passport_number and passport_number.strip():
        cleaned = passport_number.strip()
        result = await db.execute(
            select(Candidate).where(
                Candidate.passport_number == cleaned,
                Candidate.id != candidate_id,
            )
        )
        other = result.scalar_one_or_none()
        if other:
            add_warning(
                "passport_number",
                "Passport",
                other,
                "Passport number matches another candidate.",
            )

    for field, label, value in (
        ("first_name", "First name", first_name),
        ("last_name", "Last name", last_name),
        ("current_location", "Location", current_location),
        ("country", "Country", country),
        ("title", "Title", title),
    ):
        if field not in warn_fields:
            continue
        if not value or not str(value).strip():
            continue
        cleaned = str(value).strip()
        column = getattr(Candidate, field)
        result = await db.execute(
            select(Candidate).where(column == cleaned, Candidate.id != candidate_id)
        )
        other = result.scalar_one_or_none()
        if other:
            add_warning(field, label, other, f"{label} matches another candidate.")

    return warnings


async def update_candidate_profile(
    db: AsyncSession,
    candidate_id: int,
    updates: dict[str, Any],
) -> tuple[dict | None, list[dict[str, Any]]]:
    result = await db.execute(
        select(Candidate)
        .options(selectinload(Candidate.resumes))
        .where(Candidate.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        return None, []

    proposed = {
        "first_name": updates.get("first_name", candidate.first_name),
        "last_name": updates.get("last_name", candidate.last_name),
        "email": updates.get("email", candidate.email),
        "phone": updates.get("phone", candidate.phone),
        "linkedin_url": updates.get("linkedin_url", candidate.linkedin_url),
        "current_location": updates.get("current_location", candidate.current_location),
        "country": updates.get("country", candidate.country),
        "title": updates.get("title", candidate.title),
        "passport_number": updates.get("passport_number", candidate.passport_number),
    }

    warnings = await find_profile_duplicate_warnings(db, candidate_id, **proposed)

    email_warning = next((w for w in warnings if w["field"] == "email"), None)
    if email_warning:
        proposed["email"] = candidate.email

    candidate.first_name = proposed["first_name"]
    candidate.last_name = proposed["last_name"]
    candidate.email = normalize_email(proposed["email"]) or candidate.email
    candidate.phone = (proposed["phone"] or "").strip() or None
    candidate.linkedin_url = (proposed["linkedin_url"] or "").strip() or None
    candidate.current_location = (proposed["current_location"] or "").strip() or None
    candidate.country = (proposed["country"] or "").strip() or None
    candidate.title = (proposed["title"] or "").strip() or None
    candidate.passport_number = (proposed["passport_number"] or "").strip() or None
    candidate.updated_at = datetime.now(timezone.utc)

    _sync_extracted_personal_info(candidate)

    for resume in candidate.resumes:
        resume.extracted_data = candidate.extracted_data
        resume.calculated_metrics = candidate.calculated_metrics
        if resume.is_default:
            resume.candidate_email = candidate.email

    await db.flush()
    detail = await get_candidate_detail(db, candidate_id)
    return detail, warnings


async def get_candidate_detail(db: AsyncSession, candidate_id: int) -> dict | None:
    from resume_service import record_to_response

    result = await db.execute(
        select(Candidate)
        .options(selectinload(Candidate.resumes))
        .where(Candidate.id == candidate_id)
    )
    candidate = result.scalar_one_or_none()
    if not candidate:
        return None

    default_resume = next(
        (r for r in candidate.resumes if r.is_default),
        candidate.resumes[0] if candidate.resumes else None,
    )
    return {
        "id": candidate.id,
        "first_name": candidate.first_name,
        "last_name": candidate.last_name,
        "email": candidate.email,
        "phone": candidate.phone,
        "linkedin_url": candidate.linkedin_url,
        "current_location": candidate.current_location,
        "country": candidate.country,
        "title": candidate.title,
        "passport_number": candidate.passport_number,
        "extracted_data": candidate.extracted_data,
        "calculated_metrics": candidate.calculated_metrics,
        "default_resume_id": default_resume.id if default_resume else None,
        "resumes": [record_to_response(r).model_dump() for r in candidate.resumes],
        "created_at": candidate.created_at,
        "updated_at": candidate.updated_at,
    }


async def purge_orphan_candidates(db: AsyncSession) -> int:
    """Remove candidate rows with no resume attachments (ghost duplicates)."""
    result = await db.execute(
        select(Candidate).options(selectinload(Candidate.resumes))
    )
    removed = 0
    for candidate in result.scalars().unique().all():
        if not candidate.resumes:
            await db.delete(candidate)
            removed += 1
    if removed:
        await db.flush()
    return removed


async def reset_all_candidate_data(db: AsyncSession) -> dict[str, int]:
    """Delete all candidates, resumes, match results, and upload batch history."""
    from models import MatchResult, UploadBatch, UploadBatchItem

    match_count = (
        await db.execute(delete(MatchResult))
    ).rowcount or 0
    batch_item_count = (
        await db.execute(delete(UploadBatchItem))
    ).rowcount or 0
    batch_count = (
        await db.execute(delete(UploadBatch))
    ).rowcount or 0
    resume_count = (
        await db.execute(delete(ResumeRecord))
    ).rowcount or 0
    candidate_count = (
        await db.execute(delete(Candidate))
    ).rowcount or 0
    await db.flush()
    return {
        "candidates": candidate_count,
        "resumes": resume_count,
        "match_results": match_count,
        "upload_batches": batch_count,
        "upload_batch_items": batch_item_count,
    }


async def delete_candidate(db: AsyncSession, candidate_id: int) -> bool:
    from models import MatchResult

    candidate = await db.get(Candidate, candidate_id)
    if not candidate:
        return False
    await db.execute(
        delete(MatchResult).where(MatchResult.candidate_id == candidate_id)
    )
    await db.delete(candidate)
    await db.flush()
    return True


async def delete_by_resume_id(db: AsyncSession, resume_id: int) -> bool:
    """Delete a resume and its parent candidate so email/hash are fully released."""
    record = await db.get(ResumeRecord, resume_id)
    if not record:
        return False
    candidate_id = record.candidate_id
    await db.delete(record)
    await db.flush()
    if candidate_id:
        return await delete_candidate(db, candidate_id)
    return True


async def get_duplicate_settings_public(db: AsyncSession) -> dict:
    row = await ensure_duplicate_settings(db)
    return {
        "primary_fields": row.primary_fields or ["email", "phone", "linkedin_url"],
        "secondary_fields": row.secondary_fields or ["passport_number"],
        "updated_at": row.updated_at,
    }


async def update_duplicate_settings(
    db: AsyncSession, primary_fields: list[str], secondary_fields: list[str]
) -> dict:
    row = await ensure_duplicate_settings(db)
    row.primary_fields = primary_fields
    row.secondary_fields = secondary_fields
    row.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return await get_duplicate_settings_public(db)
