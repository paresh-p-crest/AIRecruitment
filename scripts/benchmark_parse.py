"""Benchmark text extraction + LLM parse on Archive sample resumes."""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

ARCHIVE = ROOT / "Archive"
SAMPLES = [
    "Nivedhidha S_Sr.Net Developer.docx",
    "Priya Boppana.Salesforce Developer.doc",
    "Khaja_Data Architect .docx",
    "Sai-Kambalapally-Sr-Java-full-stack-DEV-resume (1).docx",
]


def est_tokens(text: str) -> int:
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return max(1, len(text) // 4)


async def main() -> None:
    from database import AsyncSessionLocal, init_db
    from graph import run_extraction_pipeline
    from prescan_service import prescan_file
    from resume_parser import EXTRACTION_PROMPT, clean_resume_text
    from textract_service import extract_text_with_textract
    from utils import extract_text_from_bytes

    await init_db()

    prompt_tokens = est_tokens(EXTRACTION_PROMPT)

    print("=" * 72)
    print("RESUME PARSING BENCHMARK (Archive samples)")
    print("=" * 72)
    print(f"USE_TEXTRACT env: {os.getenv('USE_TEXTRACT', 'true')}")
    print(f"Estimated prompt template tokens: ~{prompt_tokens}")
    print()

    rows = []

    async with AsyncSessionLocal() as db:
        for name in SAMPLES:
            path = ARCHIVE / name
            if not path.exists():
                print(f"SKIP missing: {name}")
                continue

            content = path.read_bytes()
            size_kb = len(content) / 1024

            t0 = time.perf_counter()
            scan = prescan_file(name, content)
            prescan_ms = (time.perf_counter() - t0) * 1000

            t1 = time.perf_counter()
            local_text = extract_text_from_bytes(name, content)
            local_ms = (time.perf_counter() - t1) * 1000

            t2 = time.perf_counter()
            hybrid_text, source = extract_text_with_textract(content, name)
            hybrid_ms = (time.perf_counter() - t2) * 1000

            raw_chars = len(hybrid_text)
            cleaned = clean_resume_text(hybrid_text)
            input_tokens = est_tokens(cleaned)
            total_in = prompt_tokens + input_tokens

            t3 = time.perf_counter()
            try:
                result = await run_extraction_pipeline(hybrid_text, db)
                llm_ms = (time.perf_counter() - t3) * 1000
                llm_ok = result.get("parsed_json") is not None
                email = (
                    (result.get("parsed_json") or {})
                    and getattr(result["parsed_json"], "personal_info", None)
                    and result["parsed_json"].personal_info.email
                )
            except Exception as exc:
                llm_ms = (time.perf_counter() - t3) * 1000
                llm_ok = False
                email = f"ERROR: {exc}"

            rows.append(
                {
                    "file": name,
                    "kb": round(size_kb, 1),
                    "prescan_ms": round(prescan_ms, 0),
                    "local_ms": round(local_ms, 0),
                    "hybrid_ms": round(hybrid_ms, 0),
                    "source": source,
                    "chars": raw_chars,
                    "est_in_tokens": total_in,
                    "llm_ms": round(llm_ms, 0),
                    "llm_ok": llm_ok,
                    "email": email,
                    "scan": scan.status,
                    "emails_found": scan.emails_found[:1],
                }
            )

    print(f"{'File':<45} {'KB':>5} {'Src':<8} {'Chars':>6} {'~TokIn':>7} {'Pre':>6} {'Ext':>6} {'LLM':>7} {'OK'}")
    print("-" * 110)
    for r in rows:
        print(
            f"{r['file'][:44]:<45} {r['kb']:>5} {r['source'][:7]:<8} {r['chars']:>6} "
            f"{r['est_in_tokens']:>7} {r['prescan_ms']:>5.0f}ms {r['hybrid_ms']:>5.0f}ms "
            f"{r['llm_ms']:>6.0f}ms {'Y' if r['llm_ok'] else 'N'}"
        )

    if rows:
        avg_tok = sum(r["est_in_tokens"] for r in rows) / len(rows)
        avg_llm = sum(r["llm_ms"] for r in rows) / len(rows)
        print()
        print(f"Avg estimated input tokens per resume (prompt+text): ~{avg_tok:.0f}")
        print(f"Avg LLM time: ~{avg_llm:.0f} ms")
        print(f"Bulk 50 est input tokens (no dupes): ~{avg_tok * 50:.0f}")
        print()
        print("Sample prescan emails:", rows[0].get("emails_found"))


if __name__ == "__main__":
    asyncio.run(main())
