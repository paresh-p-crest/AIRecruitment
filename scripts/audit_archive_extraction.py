"""Audit text + full LLM extraction for all Archive .doc/.docx resumes."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from candidate_service import (
    enrich_calculated_metrics_from_text,
    enrich_extracted_from_raw_text,
    identity_from_extracted,
)
from database import AsyncSessionLocal
from graph import run_extraction_pipeline
from prescan_service import prescan_file
from utils import extract_text_from_bytes

ARCHIVE = ROOT / "Archive"


def archive_files() -> list[Path]:
    return sorted(
        p
        for p in ARCHIVE.iterdir()
        if p.is_file()
        and p.suffix.lower() in {".doc", ".docx"}
        and not p.name.startswith("~$")
        and "__MACOSX" not in str(p)
    )


async def audit_one(path: Path) -> dict:
    content = path.read_bytes()
    name = path.name
    row: dict = {"file": name}

    scan = prescan_file(name, content)
    row["prescan"] = scan.status
    row["emails"] = len(scan.emails_found)

    try:
        text = extract_text_from_bytes(name, content)
        row["chars"] = len(text)
    except Exception as exc:
        row["chars"] = 0
        row["error"] = f"text: {exc}"
        return row

    empty = {"Personal_Info": {}, "Education": [], "Skills": {}, "Professional_Experience": []}
    identity = identity_from_extracted(empty)
    enriched, identity = enrich_extracted_from_raw_text(empty, identity, text, filename=name)
    metrics = enrich_calculated_metrics_from_text({}, text)
    row["header_name"] = identity.get("first_name") or (enriched.get("Personal_Info") or {}).get("Name")
    row["header_years"] = metrics.get("Total_Years_Of_Experience")

    try:
        async with AsyncSessionLocal() as db:
            result = await run_extraction_pipeline(text, db)
        parsed = result["parsed_json"]
        if not parsed:
            row["llm_error"] = "no parsed_json"
            return row
        d = parsed.model_dump(by_alias=True)
        personal = d.get("Personal_Info") or {}
        skills = d.get("Skills") or {}
        row["name"] = personal.get("Name")
        row["skills"] = len(skills.get("Technical Skills") or [])
        row["education"] = len(d.get("Education") or [])
        row["experience"] = len(d.get("Professional_Experience") or [])
        row["years"] = result["calculated_metrics"].total_years_of_experience
    except Exception as exc:
        row["llm_error"] = str(exc)[:120]

    return row


async def main() -> None:
    files = archive_files()
    print(f"Auditing {len(files)} Archive resumes (text + LLM)...\n")
    print(
        f"{'File':<44} | {'chars':>5} | {'email':>5} | "
        f"{'skills':>6} | {'edu':>3} | {'exp':>3} | {'yrs':>4} | note"
    )
    print("-" * 110)

    issues: list[str] = []
    ok = 0
    for path in files:
        row = await audit_one(path)
        note = ""
        if row.get("llm_error"):
            note = row["llm_error"]
            issues.append(f"{row['file']}: {note}")
        elif row.get("error"):
            note = row["error"]
            issues.append(f"{row['file']}: {note}")
        elif row.get("prescan") == "error":
            note = "prescan fail"
            issues.append(f"{row['file']}: prescan")
        elif (row.get("skills") or 0) == 0 and (row.get("experience") or 0) == 0:
            note = "sparse LLM"
            issues.append(f"{row['file']}: sparse")
        else:
            ok += 1

        print(
            f"{row['file'][:44]:<44} | {row.get('chars', 0):>5} | "
            f"{row.get('emails', 0):>5} | {row.get('skills', 0) or 0:>6} | "
            f"{row.get('education', 0) or 0:>3} | {row.get('experience', 0) or 0:>3} | "
            f"{row.get('years', 0) or 0:>4.1f} | {note[:30]}"
        )

    print(f"\nOK (skills+experience): {ok}/{len(files)}")
    if issues:
        print(f"Issues: {len(issues)}")
        for item in issues:
            print(f"  - {item}")


if __name__ == "__main__":
    asyncio.run(main())
