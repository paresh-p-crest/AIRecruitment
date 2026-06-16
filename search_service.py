"""Natural-language candidate search across all profiles."""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from llm_factory import build_llm_from_settings
from models import Candidate
from resume_parser import extract_json_from_text
from settings_service import get_effective_settings


def _candidate_name(candidate: Candidate) -> str:
    parts = [candidate.first_name, candidate.last_name]
    name = " ".join(p for p in parts if p)
    if name:
        return name
    return (candidate.extracted_data or {}).get("Personal_Info", {}).get("Name") or "Unknown"


def _tokenize(text: str) -> set[str]:
    return {
        t.lower()
        for t in re.findall(r"[a-zA-Z0-9+#.\-]+", text.lower())
        if len(t) >= 2
    }


def _candidate_search_blob(candidate: Candidate) -> str:
    data = candidate.extracted_data or {}
    parts: list[str] = [
        candidate.title or "",
        candidate.email or "",
        candidate.current_location or "",
        candidate.country or "",
    ]
    personal = data.get("Personal_Info") or {}
    parts.append(str(personal.get("Current Designation") or ""))

    skills = data.get("Skills") or {}
    if isinstance(skills, dict):
        parts.extend(skills.get("Technical_Skills") or [])
        parts.extend(skills.get("Soft_Skills") or [])

    for edu in data.get("Education") or []:
        if isinstance(edu, dict):
            parts.extend(
                str(edu.get(k) or "")
                for k in ("Degree", "Specialisation", "College", "End Year")
            )

    for exp in data.get("Professional_Experience") or []:
        if isinstance(exp, dict):
            parts.extend(
                str(exp.get(k) or "")
                for k in ("Job Title", "Company Name", "Employment Type")
            )
            parts.extend(exp.get("Technologies Used") or [])

    metrics = candidate.calculated_metrics or {}
    yrs = metrics.get("Total_Years_Of_Experience")
    if yrs is not None:
        parts.append(f"{yrs} years experience")

    default_resume = next(
        (r for r in candidate.resumes if r.is_default),
        candidate.resumes[0] if candidate.resumes else None,
    )
    if default_resume and default_resume.raw_text:
        parts.append(default_resume.raw_text[:3000])

    return " ".join(str(p) for p in parts if p)


def _score_candidate(query_tokens: set[str], blob: str) -> float:
    if not query_tokens:
        return 0.0
    blob_lower = blob.lower()
    blob_tokens = _tokenize(blob)
    overlap = query_tokens & blob_tokens
    phrase_bonus = sum(1 for t in query_tokens if t in blob_lower and len(t) > 3)
    return len(overlap) * 2 + phrase_bonus


def _build_candidate_summary(candidate: Candidate) -> dict[str, Any]:
    data = candidate.extracted_data or {}
    skills = data.get("Skills") or {}
    tech = []
    if isinstance(skills, dict):
        tech = (skills.get("Technical_Skills") or [])[:12]
    metrics = candidate.calculated_metrics or {}
    default_resume = next(
        (r for r in candidate.resumes if r.is_default),
        candidate.resumes[0] if candidate.resumes else None,
    )
    return {
        "candidate_id": candidate.id,
        "resume_id": default_resume.id if default_resume else None,
        "name": _candidate_name(candidate),
        "email": candidate.email,
        "phone": candidate.phone,
        "title": candidate.title,
        "location": candidate.current_location,
        "years_experience": metrics.get("Total_Years_Of_Experience"),
        "skills": tech,
        "education": [
            {
                "degree": e.get("Degree"),
                "college": e.get("College"),
            }
            for e in (data.get("Education") or [])[:3]
            if isinstance(e, dict)
        ],
    }


def _find_candidates_by_name_mention(
    query: str, candidates: list[Candidate]
) -> list[Candidate]:
    q = query.lower()
    matches: list[Candidate] = []
    for candidate in candidates:
        name = _candidate_name(candidate).lower()
        if not name or name == "unknown":
            continue
        parts = [p for p in name.split() if len(p) > 2]
        if len(parts) >= 2 and all(p in q for p in parts):
            matches.append(candidate)
        elif len(parts) == 1 and parts[0] in q:
            matches.append(candidate)
    return matches


def _merge_scored_candidates(
    scored: list[tuple[float, Candidate, dict[str, Any]]],
    extra: list[Candidate],
    *,
    base_score: float = 50.0,
) -> list[tuple[float, Candidate, dict[str, Any]]]:
    seen = {c.id for _, c, _ in scored}
    merged = list(scored)
    for candidate in extra:
        if candidate.id in seen:
            continue
        merged.append((base_score, candidate, _build_candidate_summary(candidate)))
        seen.add(candidate.id)
    merged.sort(key=lambda x: x[0], reverse=True)
    return merged


async def search_candidates(
    db: AsyncSession,
    query: str,
    limit: int = 15,
    *,
    context: list[dict[str, str]] | None = None,
    previous_result_ids: list[int] | None = None,
) -> dict[str, Any]:
    query = query.strip()
    if not query:
        return {"query": query, "summary": "Enter a search question.", "results": []}

    result = await db.execute(
        select(Candidate).options(selectinload(Candidate.resumes))
    )
    candidates = result.scalars().unique().all()
    if not candidates:
        return {
            "query": query,
            "summary": "No candidates in the database yet.",
            "results": [],
        }

    query_tokens = _tokenize(query)
    scored: list[tuple[float, Candidate, dict[str, Any]]] = []
    for candidate in candidates:
        blob = _candidate_search_blob(candidate)
        score = _score_candidate(query_tokens, blob)
        if score > 0:
            scored.append((score, candidate, _build_candidate_summary(candidate)))

    scored.sort(key=lambda x: x[0], reverse=True)

    previous_ids = previous_result_ids or []
    if previous_ids:
        id_set = set(previous_ids)
        previous_candidates = [c for c in candidates if c.id in id_set]
        scored = _merge_scored_candidates(scored, previous_candidates, base_score=40.0)

    name_matches = _find_candidates_by_name_mention(query, candidates)
    if name_matches:
        scored = _merge_scored_candidates(scored, name_matches, base_score=60.0)

    top = scored[: max(limit, 20)]

    context_lines = ""
    if context:
        context_lines = "\n".join(
            f"{msg.get('role', 'user').upper()}: {msg.get('content', '')}"
            for msg in context[-6:]
            if msg.get("content")
        )

    if not top and not context_lines:
        return {
            "query": query,
            "summary": "No candidates matched your query. Try different skills or keywords.",
            "results": [],
        }

    if not top and context_lines:
        top = [
            (30.0, c, _build_candidate_summary(c))
            for c in candidates[: min(10, len(candidates))]
        ]

    settings = await get_effective_settings(db)
    llm = build_llm_from_settings(settings)

    payload = [{"relevance_score": s, **summary} for s, _, summary in top[:20]]
    history_block = ""
    if context_lines:
        history_block = f"""
Recent conversation:
{context_lines}

The latest user message may refer to candidates from earlier results. Answer follow-up questions
about specific people by name when possible.
"""
    prompt = f"""You are a recruitment search assistant.{history_block}
User question:
"{query}"

Here are candidate profiles (JSON). Rank and return the best matches, or answer a follow-up about a named candidate.

Return ONLY valid JSON with this shape:
{{
  "summary": "One short sentence answering the user (for follow-ups about one person, answer yes/no or explain in summary)",
  "results": [
    {{
      "candidate_id": number,
      "resume_id": number or null,
      "name": string,
      "email": string,
      "phone": string or null,
      "title": string or null,
      "match_reason": "short why they match or answer about skills",
      "relevance_score": number 0-100
    }}
  ]
}}

For skill check follow-ups about one person, include only that candidate in results if they match the question.
Include at most {limit} results, best first. Use only candidates from the input list.

Candidates:
{json.dumps(payload, default=str)[:12000]}
"""

    try:
        response = await llm.ainvoke(prompt)
        content = getattr(response, "content", str(response))
        if isinstance(content, list):
            content = " ".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
            )
        parsed = extract_json_from_text(str(content))
        summary = str(parsed.get("summary") or "Search completed.")
        results = parsed.get("results") or []
        if not isinstance(results, list):
            results = []
    except Exception as exc:
        summary = f"Keyword matches found (LLM summary unavailable: {exc})"
        results = [
            {
                "candidate_id": summary_row["candidate_id"],
                "resume_id": summary_row.get("resume_id"),
                "name": summary_row["name"],
                "email": summary_row["email"],
                "phone": summary_row.get("phone"),
                "title": summary_row.get("title"),
                "match_reason": f"Matched keywords in profile (score {int(score)})",
                "relevance_score": min(100, int(score * 10)),
            }
            for score, _, summary_row in top[:limit]
        ]

    cleaned: list[dict[str, Any]] = []
    for row in results[:limit]:
        if not isinstance(row, dict):
            continue
        cid = row.get("candidate_id")
        if cid is None:
            continue
        cleaned.append(
            {
                "candidate_id": int(cid),
                "resume_id": row.get("resume_id"),
                "name": row.get("name") or "Unknown",
                "email": row.get("email"),
                "phone": row.get("phone"),
                "title": row.get("title"),
                "match_reason": row.get("match_reason") or "Matched profile",
                "relevance_score": row.get("relevance_score"),
            }
        )

    return {"query": query, "summary": summary, "results": cleaned}
