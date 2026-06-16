"""AWS Textract text extraction with local-parser fallback (PDF only)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from utils import extract_text_from_bytes

logger = logging.getLogger(__name__)

_TEXTRACT_EXTENSIONS = {".pdf"}


def _textract_client():
    import boto3

    region = os.getenv("AWS_REGION", "us-east-1")
    return boto3.client("textract", region_name=region)


def _lines_from_textract_response(response: dict) -> str:
    lines: list[str] = []
    for block in response.get("Blocks", []):
        if block.get("BlockType") == "LINE" and block.get("Text"):
            lines.append(block["Text"])
    return "\n".join(lines).strip()


def _use_textract_for_file(filename: str) -> bool:
    """Textract supports PDF/images — skip DOC/DOCX to avoid API errors and cost."""
    extension = Path(filename or "").suffix.lower()
    return extension in _TEXTRACT_EXTENSIONS


def extract_text_with_textract(content: bytes, filename: str) -> tuple[str, str]:
    """
    Extract plain text: Textract for PDF when enabled, local parsers otherwise.

    Returns (text, source) where source is 'textract' or 'local'.
    """
    if not _use_textract_for_file(filename):
        return extract_text_from_bytes(filename, content), "local"

    use_textract = os.getenv("USE_TEXTRACT", "true").lower() in {"1", "true", "yes"}
    if not use_textract:
        return extract_text_from_bytes(filename, content), "local"

    try:
        client = _textract_client()
        response = client.detect_document_text(Document={"Bytes": content})
        text = _lines_from_textract_response(response)
        if text:
            return text, "textract"
        logger.warning("Textract returned empty text for %s; using local fallback", filename)
    except Exception as exc:
        logger.warning("Textract failed for %s: %s — using local fallback", filename, exc)

    return extract_text_from_bytes(filename, content), "local"
