"""Regex-based contact field extraction from resume text (no app imports)."""

from __future__ import annotations

import re

EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)
MAILTO_PATTERN = re.compile(
    r"mailto:([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})",
    re.IGNORECASE,
)
PHONE_PATTERN = re.compile(
    r"(?:\+?\d{1,3}[\s\-.]?)?(?:\(?\d{2,4}\)?[\s\-.]?)?\d{3,4}[\s\-.]?\d{3,4}(?:[\s\-.]?\d{1,6})?"
)
LINKEDIN_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/(?:in|pub)/[a-zA-Z0-9\-_%]+/?",
    re.IGNORECASE,
)


def normalize_email(email: str | None) -> str | None:
    if not email or "@" not in str(email):
        return None
    normalized = str(email).strip().lower()
    return normalized or None


def _sanitize_text_for_contact_scan(text: str) -> str:
    """Strip invisible chars and Word hyperlink noise before regex scans."""
    cleaned = (text or "").replace("\x00", " ")
    cleaned = cleaned.replace("\u200b", "").replace("\ufeff", "")
    cleaned = re.sub(
        r'HYPERLINK\s+"mailto:([^"]+)"\s*',
        r"\1 ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"HYPERLINK\s+\"[^\"]+\"\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"mailto:", "", cleaned, flags=re.IGNORECASE)
    return cleaned


def extract_emails_from_text(text: str) -> list[str]:
    sanitized = _sanitize_text_for_contact_scan(text)
    found = EMAIL_PATTERN.findall(sanitized)
    found.extend(MAILTO_PATTERN.findall(sanitized))

    normalized: list[str] = []
    seen: set[str] = set()
    for email in found:
        key = normalize_email(email)
        if key and key not in seen:
            seen.add(key)
            normalized.append(key)
    return normalized


def _normalize_phone(value: str) -> str | None:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) < 10:
        return None
    return digits


def extract_phones_from_text(text: str) -> list[str]:
    found = PHONE_PATTERN.findall(text or "")
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in found:
        key = _normalize_phone(raw)
        if key and key not in seen:
            seen.add(key)
            normalized.append(key)
    return normalized


def extract_linkedin_urls_from_text(text: str) -> list[str]:
    found = LINKEDIN_PATTERN.findall(text or "")
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in found:
        url = raw.strip().rstrip("/")
        if not url.lower().startswith("http"):
            url = f"https://{url.lstrip('/')}"
        key = url.lower()
        if key not in seen:
            seen.add(key)
            normalized.append(url)
    return normalized
