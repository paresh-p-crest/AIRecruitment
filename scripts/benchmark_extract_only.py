"""Quick benchmark: prescan + local text extraction on Archive .doc/.docx (no LLM)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from doc_converter import extract_text_from_doc
from prescan_service import prescan_file
from utils import extract_text_from_bytes, extract_text_from_docx

ARCHIVE = ROOT / "Archive"


def extract_local(path: Path, content: bytes) -> tuple[str, str]:
    ext = path.suffix.lower()
    if ext == ".docx":
        return extract_text_from_docx(content), "docx"
    if ext == ".doc":
        text, method = extract_text_from_doc(content, path.name)
        return text, method
    return extract_text_from_bytes(path.name, content), "bytes"


def main() -> None:
    if not ARCHIVE.is_dir():
        print(f"Archive folder not found: {ARCHIVE}")
        sys.exit(1)

    files = sorted(
        p
        for p in ARCHIVE.iterdir()
        if p.is_file()
        and p.suffix.lower() in {".pdf", ".docx", ".doc"}
        and not p.name.startswith("~$")
        and "__MACOSX" not in str(p)
    )

    print(f"Local extraction benchmark — {len(files)} files from Archive\n")
    print(f"{'File':<42} | {'Method':<14} | {'Chars':>6} | Scan ms | Ext ms | Status")
    print("-" * 95)

    ok = 0
    total_ext_ms = 0.0
    for path in files:
        content = path.read_bytes()
        t0 = time.perf_counter()
        scan = prescan_file(path.name, content)
        prescan_ms = (time.perf_counter() - t0) * 1000

        t1 = time.perf_counter()
        try:
            text, method = extract_local(path, content)
            status = "ok" if len(text) > 80 else "short"
            if status == "ok":
                ok += 1
        except Exception as exc:
            text, method, status = "", "error", str(exc)[:20]
        ext_ms = (time.perf_counter() - t1) * 1000
        total_ext_ms += ext_ms

        print(
            f"{path.name[:42]:<42} | {method[:14]:<14} | {len(text):>6} | "
            f"{prescan_ms:>6.0f} | {ext_ms:>5.0f} | {status}"
        )

    n = len(files) or 1
    print(f"\nParsed OK: {ok}/{len(files)}")
    print(f"Avg extraction: {total_ext_ms / n:.0f} ms per file (local parsers only)")


if __name__ == "__main__":
    main()
