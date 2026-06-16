"""Pre-AI gatekeeper scan: SHA-256, regex email, batch duplicate detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from contact_extract import (
    extract_emails_from_text,
    extract_linkedin_urls_from_text,
    extract_phones_from_text,
    normalize_email,
)
from resume_service import compute_file_hash
from utils import extract_text_from_bytes, validate_resume_bytes

MAX_BULK_FILES = 50

ScanStatus = Literal["ok", "warning", "error"]


@dataclass
class PrescanFileResult:
    filename: str
    file_hash: str
    status: ScanStatus
    emails_found: list[str] = field(default_factory=list)
    phones_found: list[str] = field(default_factory=list)
    linkedin_urls_found: list[str] = field(default_factory=list)
    message: str | None = None
    duplicate_of_filename: str | None = None
    duplicate_in_database: bool = False
    skipped_ai: bool = True
    processable: bool = False


@dataclass
class PrescanReport:
    total: int
    ready: int
    warnings: int
    errors: int
    can_proceed: bool
    results: list[PrescanFileResult]


def prescan_file(filename: str, content: bytes) -> PrescanFileResult:
    """Scan one file without AI — hash + regex email on quick local text."""
    safe_name = filename or "unknown"
    file_hash = compute_file_hash(content)

    try:
        validate_resume_bytes(safe_name, content)
        text = extract_text_from_bytes(safe_name, content)
    except ValueError as exc:
        return PrescanFileResult(
            filename=safe_name,
            file_hash=file_hash,
            status="error",
            message=str(exc),
        )

    emails = extract_emails_from_text(text)
    phones = extract_phones_from_text(text)
    linkedin_urls = extract_linkedin_urls_from_text(text)
    if not emails:
        return PrescanFileResult(
            filename=safe_name,
            file_hash=file_hash,
            status="error",
            emails_found=[],
            phones_found=phones,
            linkedin_urls_found=linkedin_urls,
            message="No email address found in resume. Email is required to add a candidate.",
            skipped_ai=True,
        )

    return PrescanFileResult(
        filename=safe_name,
        file_hash=file_hash,
        status="ok",
        emails_found=emails,
        phones_found=phones,
        linkedin_urls_found=linkedin_urls,
        skipped_ai=True,
        processable=True,
    )


def _finalize_processable(result: PrescanFileResult) -> PrescanFileResult:
    """Batch duplicates are skipped; DB duplicates proceed with the chosen policy."""
    if result.status == "ok":
        result.processable = True
    elif result.status == "warning" and not result.duplicate_of_filename:
        result.processable = True
    else:
        result.processable = False
    return result


def prescan_batch(
    files: list[tuple[str, bytes]],
    *,
    existing_hashes: set[str] | None = None,
    existing_emails: set[str] | None = None,
    existing_phones: set[str] | None = None,
    existing_linkedin_urls: set[str] | None = None,
) -> PrescanReport:
    """Scan up to 50 files and flag intra-batch / DB duplicates."""
    if len(files) > MAX_BULK_FILES:
        raise ValueError(f"A maximum of {MAX_BULK_FILES} files can be scanned at once.")

    existing_hashes = existing_hashes or set()
    existing_emails = existing_emails or set()
    existing_phones = existing_phones or set()
    existing_linkedin_urls = {u.lower() for u in (existing_linkedin_urls or set())}
    seen_hashes: dict[str, str] = {}
    seen_emails: dict[str, str] = {}
    seen_phones: dict[str, str] = {}
    seen_linkedin: dict[str, str] = {}

    results: list[PrescanFileResult] = []

    for filename, content in files:
        result = prescan_file(filename, content)

        if result.status == "error" and not result.emails_found:
            results.append(result)
            continue

        if result.file_hash in existing_hashes:
            result.status = "warning"
            result.duplicate_in_database = True
            result.message = (
                "Identical file already exists in the database. "
                "Choose a duplicate policy before processing."
            )
            results.append(_finalize_processable(result))
            continue

        if result.file_hash in seen_hashes:
            result.status = "warning"
            result.duplicate_of_filename = seen_hashes[result.file_hash]
            result.message = (
                f"Duplicate file in upload batch (same as '{result.duplicate_of_filename}'). "
                "Will be skipped; other files can still be processed."
            )
            results.append(_finalize_processable(result))
            continue

        seen_hashes[result.file_hash] = result.filename

        primary_email = result.emails_found[0] if result.emails_found else None
        primary_phone = result.phones_found[0] if result.phones_found else None

        if primary_email:
            if primary_email in existing_emails:
                result.status = "warning"
                result.duplicate_in_database = True
                result.message = (
                    f"Email '{primary_email}' already exists in the database. "
                    "Choose a duplicate policy before processing."
                )
            elif primary_email in seen_emails:
                result.status = "warning"
                result.duplicate_of_filename = seen_emails[primary_email]
                result.message = (
                    f"Duplicate email in upload batch (same as '{result.duplicate_of_filename}'). "
                    "Will be skipped; other files can still be processed."
                )

        if result.status in {"ok", "warning"} and primary_phone:
            if primary_phone in existing_phones:
                result.status = "warning"
                result.duplicate_in_database = True
                result.message = (
                    f"Phone '{primary_phone}' already exists in the database. "
                    "Choose a duplicate policy before processing."
                )
            elif primary_phone in seen_phones:
                result.status = "warning"
                result.duplicate_of_filename = seen_phones[primary_phone]
                result.message = (
                    f"Duplicate phone in upload batch (same as '{result.duplicate_of_filename}'). "
                    "Will be skipped; other files can still be processed."
                )

        if result.status == "ok" and primary_email:
            seen_emails[primary_email] = result.filename
        if result.status in {"ok", "warning"} and primary_phone:
            seen_phones[primary_phone] = result.filename

        primary_linkedin = (
            result.linkedin_urls_found[0].lower() if result.linkedin_urls_found else None
        )
        if result.status in {"ok", "warning"} and primary_linkedin:
            if primary_linkedin in existing_linkedin_urls:
                result.status = "warning"
                result.duplicate_in_database = True
                result.message = (
                    "LinkedIn URL already exists in the database. "
                    "Choose a duplicate policy before processing."
                )
            elif primary_linkedin in seen_linkedin:
                result.status = "warning"
                result.duplicate_of_filename = seen_linkedin[primary_linkedin]
                result.message = (
                    f"Duplicate LinkedIn in upload batch (same as '{result.duplicate_of_filename}'). "
                    "Will be skipped; other files can still be processed."
                )
            else:
                seen_linkedin[primary_linkedin] = result.filename

        results.append(_finalize_processable(result))

    ready = sum(1 for r in results if r.status == "ok")
    warnings = sum(1 for r in results if r.status == "warning")
    errors = sum(1 for r in results if r.status == "error")

    return PrescanReport(
        total=len(results),
        ready=ready,
        warnings=warnings,
        errors=errors,
        can_proceed=any(r.processable for r in results),
        results=results,
    )
