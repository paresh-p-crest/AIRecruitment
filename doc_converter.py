"""Extract text from legacy .doc files — no LibreOffice required on production."""

from __future__ import annotations

import io
import logging
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)

_WINDOWS_SOFFICE_PATHS = (
    Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
    Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
)

_UTF16_ASCII_RUN = re.compile(rb"(?:[\x20-\x7e]\x00){4,}")


def find_libreoffice_executable() -> Path | None:
    """Resolve LibreOffice soffice when installed (optional fallback)."""
    env_path = os.getenv("LIBREOFFICE_PATH", "").strip()
    if env_path:
        candidate = Path(env_path)
        if candidate.is_file():
            return candidate

    which = shutil.which("soffice")
    if which:
        return Path(which)

    for candidate in _WINDOWS_SOFFICE_PATHS:
        if candidate.is_file():
            return candidate

    return None


def is_libreoffice_available() -> bool:
    return find_libreoffice_executable() is not None


def find_antiword_executable() -> str | None:
    env_path = os.getenv("ANTIWORD_PATH", "").strip()
    if env_path and Path(env_path).is_file():
        return env_path
    return shutil.which("antiword")


def is_antiword_available() -> bool:
    return find_antiword_executable() is not None


def is_tika_available() -> bool:
    if os.getenv("DISABLE_TIKA", "").lower() in {"1", "true", "yes"}:
        return False
    if shutil.which("java") is None:
        return False
    try:
        import tika  # noqa: F401

        return True
    except ImportError:
        return False


def is_ole_fallback_enabled() -> bool:
    return os.getenv("DISABLE_DOC_OLE_FALLBACK", "").lower() not in {"1", "true", "yes"}


def is_office_oxide_available() -> bool:
    if os.getenv("DISABLE_OFFICE_OXIDE", "").lower() in {"1", "true", "yes"}:
        return False
    try:
        import office_oxide  # noqa: F401

        return True
    except ImportError:
        return False


def is_sharepoint2text_available() -> bool:
    if os.getenv("DISABLE_SHAREPOINT2TEXT", "").lower() in {"1", "true", "yes"}:
        return False
    try:
        import sharepoint2text  # noqa: F401

        return True
    except ImportError:
        return False


def get_doc_extraction_capabilities() -> dict[str, bool]:
    """Report which .doc extraction backends are available on this host."""
    return {
        "antiword": is_antiword_available(),
        "office_oxide": is_office_oxide_available(),
        "sharepoint2text": is_sharepoint2text_available(),
        "tika": is_tika_available(),
        "libreoffice": is_libreoffice_available(),
        "ole_fallback": is_ole_fallback_enabled(),
    }


def can_extract_doc() -> bool:
    caps = get_doc_extraction_capabilities()
    return any(caps.values())


def _extract_doc_antiword(content: bytes, filename: str) -> str:
    antiword = find_antiword_executable()
    if not antiword:
        raise RuntimeError("antiword is not installed")

    safe_name = Path(filename).name or "resume.doc"
    if not safe_name.lower().endswith(".doc"):
        safe_name = f"{Path(safe_name).stem}.doc"

    with tempfile.TemporaryDirectory(prefix="resume-antiword-") as tmpdir:
        input_path = Path(tmpdir) / safe_name
        input_path.write_bytes(content)
        result = subprocess.run(
            [antiword, "-m", "UTF-8.txt", str(input_path)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if result.returncode != 0:
            stderr = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(stderr or "antiword failed")
        text = (result.stdout or "").strip()
        if not text:
            raise RuntimeError("antiword returned empty text")
        return text


def _extract_doc_office_oxide(content: bytes, filename: str) -> str:
    if not is_office_oxide_available():
        raise RuntimeError("office-oxide is not installed (pip install office-oxide)")

    from office_oxide import Document

    with Document.from_bytes(content, "doc") as document:
        text = document.plain_text().strip()
    if not text:
        raise RuntimeError("office-oxide returned empty text")
    logger.info("Extracted .doc text via office-oxide for %s", filename)
    return text


def _extract_doc_sharepoint2text(content: bytes, filename: str) -> str:
    if not is_sharepoint2text_available():
        raise RuntimeError("sharepoint-to-text is not installed")

    import sharepoint2text

    extension = Path(filename).suffix.lower() or ".doc"
    result = next(
        sharepoint2text.read_bytes(
            content,
            extension=extension,
            ignore_images=True,
        )
    )
    text = result.get_full_text().strip()
    if not text:
        raise RuntimeError("sharepoint-to-text returned empty text")
    logger.info("Extracted .doc text via sharepoint-to-text for %s", filename)
    return text


def _extract_doc_tika(content: bytes, filename: str) -> str:
    if not is_tika_available():
        raise RuntimeError("Apache Tika is not available (install Java + pip package tika)")

    from tika import parser as tika_parser

    parsed = tika_parser.from_buffer(content, requestOptions={"timeout": 120000})
    text = (parsed.get("content") or "").strip()
    if not text:
        raise RuntimeError("Tika returned empty text")
    logger.info("Extracted .doc text via Apache Tika for %s", filename)
    return text


def _extract_doc_ole_fallback(content: bytes, filename: str = "resume.doc") -> str:
    import olefile

    if not olefile.isOleFile(io.BytesIO(content)):
        raise RuntimeError("File is not a valid OLE .doc document")

    ole = olefile.OleFileIO(io.BytesIO(content))
    if not ole.exists("WordDocument"):
        raise RuntimeError("WordDocument stream missing")

    data = ole.openstream("WordDocument").read()
    chunks = [
        match.decode("utf-16le")
        for match in _UTF16_ASCII_RUN.findall(data)
    ]
    text = "\n".join(chunk.strip() for chunk in chunks if chunk.strip())
    if not text:
        raise RuntimeError("OLE fallback found no readable text")
    logger.info("Extracted .doc text via OLE UTF-16 fallback")
    return text


def convert_doc_to_docx(content: bytes, filename: str = "resume.doc") -> bytes:
    """Convert .doc to .docx via LibreOffice when installed (optional)."""
    soffice = find_libreoffice_executable()
    if soffice is None:
        raise RuntimeError(
            "LibreOffice is not installed. Use direct .doc text extraction instead."
        )

    safe_name = Path(filename).name or "resume.doc"
    if not safe_name.lower().endswith(".doc"):
        safe_name = f"{Path(safe_name).stem}.doc"

    with tempfile.TemporaryDirectory(prefix="resume-doc-") as tmpdir:
        tmp_path = Path(tmpdir)
        input_path = tmp_path / safe_name
        input_path.write_bytes(content)

        command = [
            str(soffice),
            "--headless",
            "--norestore",
            "--convert-to",
            "docx",
            "--outdir",
            str(tmp_path),
            str(input_path),
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("LibreOffice timed out while converting .doc file.") from exc

        if result.returncode != 0:
            stderr = (result.stderr or result.stdout or "").strip()
            logger.error("LibreOffice conversion failed: %s", stderr)
            raise RuntimeError(
                f"Failed to convert .doc file. LibreOffice error: {stderr or 'unknown error'}"
            )

        output_path = input_path.with_suffix(".docx")
        if not output_path.is_file():
            docx_files = sorted(tmp_path.glob("*.docx"))
            if not docx_files:
                raise RuntimeError("LibreOffice did not produce a .docx output file.")
            output_path = docx_files[0]

        return output_path.read_bytes()


def _extract_doc_libreoffice(content: bytes, filename: str) -> str:
    from docx import Document

    docx_content = convert_doc_to_docx(content, filename)
    document = Document(io.BytesIO(docx_content))
    text = "\n".join(
        paragraph.text.strip()
        for paragraph in document.paragraphs
        if paragraph.text.strip()
    ).strip()
    if not text:
        raise RuntimeError("No text after LibreOffice conversion")
    logger.info("Extracted .doc text via LibreOffice for %s", filename)
    return text


def extract_text_from_doc(content: bytes, filename: str = "resume.doc") -> tuple[str, str]:
    """
    Extract plain text from a legacy .doc file.

    Tries, in order: antiword → office-oxide → sharepoint-to-text → Tika →
    LibreOffice (optional) → OLE fallback.
    Returns (text, method_name).
    """
    errors: list[str] = []
    methods: list[tuple[str, Callable[[bytes, str], str]]] = []

    # office-oxide first — fast pure-Python path for Windows/Linux demos.
    if is_office_oxide_available():
        methods.append(("office_oxide", _extract_doc_office_oxide))
    if is_antiword_available():
        methods.append(("antiword", _extract_doc_antiword))
    if is_sharepoint2text_available():
        methods.append(("sharepoint2text", _extract_doc_sharepoint2text))
    if is_tika_available():
        methods.append(("tika", _extract_doc_tika))
    if is_libreoffice_available():
        methods.append(("libreoffice", _extract_doc_libreoffice))
    if is_ole_fallback_enabled():
        methods.append(("ole_fallback", _extract_doc_ole_fallback))

    for name, method in methods:
        try:
            text = method(content, filename)
            if text and text.strip():
                return text.strip(), name
        except Exception as exc:
            logger.debug(".doc extraction via %s failed for %s: %s", name, filename, exc)
            errors.append(f"{name}: {exc}")

    hint = (
        "pip install office-oxide (recommended), or antiword on Linux "
        "(apt install antiword), or upload .docx / .pdf instead."
    )
    detail = "; ".join(errors) if errors else "no .doc extractors configured"
    raise RuntimeError(f"Could not extract text from .doc file. {detail}. {hint}")
