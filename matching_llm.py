"""LLM narrative layer for hybrid resume matching."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from jd_parser import ParsedJobDescription
from llm_factory import build_llm_from_settings
from matching_engine import RuleMatchResult
from resume_parser import extract_json_from_text
from settings_service import get_effective_settings

MATCH_NARRATIVE_PROMPT = """You are an expert technical recruiter. Given a job description summary, candidate summary, and rule-based match scores, write a concise hiring analysis.

Return ONLY valid JSON with this shape:
{{
  "strengths": ["bullet 1", "bullet 2"],
  "weaknesses": ["bullet 1", "bullet 2"],
  "summary": "2-3 sentence narrative for the hiring manager"
}}

Job title: {job_title}
Minimum experience (years): {min_years}
Required skills: {required_skills}
Preferred skills: {preferred_skills}

Candidate: {candidate_name}
Total experience (years): {total_years}
Matching skills: {matching_skills}
Missing skills: {missing_skills}
Rule-based final score: {final_score}/100
Component scores: {component_scores}
Red flags: {red_flags}

Keep strengths and weaknesses factual and specific. Do not invent credentials not implied by the data.
"""


async def generate_match_narrative(
    db: AsyncSession,
    jd: ParsedJobDescription,
    record,
    rule_result: RuleMatchResult,
) -> dict[str, Any]:
    """Use the configured LLM to produce strengths, weaknesses, and summary."""
    extracted = record.extracted_data or {}
    personal = extracted.get("Personal_Info", {}) or {}
    metrics = record.calculated_metrics or {}

    prompt = MATCH_NARRATIVE_PROMPT.format(
        job_title=jd.job_title or "Role",
        min_years=jd.min_years_experience if jd.min_years_experience is not None else "Not specified",
        required_skills=", ".join(jd.required_skills[:15]) or "See description",
        preferred_skills=", ".join(jd.preferred_skills[:10]) or "None listed",
        candidate_name=personal.get("Name") or record.filename,
        total_years=metrics.get("Total_Years_Of_Experience", 0),
        matching_skills=", ".join(rule_result.matching_skills[:12]) or "None",
        missing_skills=", ".join(rule_result.missing_skills[:12]) or "None",
        final_score=rule_result.final_score,
        component_scores=json.dumps(rule_result.component_scores),
        red_flags=", ".join(flag.description for flag in rule_result.red_flags) or "None",
    )

    settings = await get_effective_settings(db)
    llm = build_llm_from_settings(settings)
    response = await llm.ainvoke(prompt)
    content = getattr(response, "content", str(response))
    if isinstance(content, list):
        content = " ".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )

    try:
        payload = extract_json_from_text(str(content))
    except (json.JSONDecodeError, ValueError, TypeError):
        return {
            "strengths": [],
            "weaknesses": [],
            "summary": str(content).strip()[:500],
        }

    return {
        "strengths": _as_str_list(payload.get("strengths")),
        "weaknesses": _as_str_list(payload.get("weaknesses")),
        "summary": str(payload.get("summary") or "").strip(),
    }


def _as_str_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []
