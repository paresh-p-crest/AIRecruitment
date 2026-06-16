"""LangGraph extraction pipeline: LLM structured output + business metrics."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import TypedDict

from dotenv import load_dotenv
from langgraph.graph import END, StateGraph
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from extraction_chunked import (
    extract_resume_data_chunked,
    should_use_chunked_extraction,
)
from llm_factory import build_llm_from_settings
from contact_extract import (
    extract_emails_from_text,
    extract_phones_from_text,
    normalize_email,
)
from resume_parser import (
    EXTRACTION_PROMPT,
    clean_resume_text,
    extract_json_from_text,
    parse_extracted_resume,
)
from schemas import CalculatedMetrics, ExtractedResume
from settings_service import get_active_model_name, get_effective_settings

load_dotenv()


class GraphState(TypedDict):
    raw_text: str
    parsed_json: ExtractedResume | None
    calculated_metrics: CalculatedMetrics | None


def _parse_date(value: str | None) -> datetime | None:
    """Best-effort parser for common resume date formats."""
    if not value:
        return None

    normalized = value.strip().lower()
    # Strip trailing duration hints e.g. "Present (1 year 4 months)"
    normalized = re.sub(r"\s*\(.*?\)\s*", " ", normalized).strip()

    if normalized in {"present", "current", "now", "ongoing"}:
        return datetime.now()

    cleaned = re.sub(r"\b(to|–|—|-)\b", " ", normalized)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    formats = (
        "%b %Y",
        "%B %Y",
        "%m/%Y",
        "%m-%Y",
        "%Y-%m",
        "%Y/%m",
        "%Y",
    )
    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue

    year_match = re.search(r"(19|20)\d{2}", cleaned)
    if year_match:
        return datetime(int(year_match.group()), 1, 1)

    return None


def _calculate_total_years(experiences: list) -> float:
    """Sum employment durations; merge overlapping roles."""
    intervals: list[tuple[datetime, datetime]] = []

    for entry in experiences:
        start = _parse_date(entry.start_date)
        end = _parse_date(entry.end_date)
        if not start or not end or end < start:
            continue
        intervals.append((start, end))

    if not intervals:
        return 0.0

    intervals.sort(key=lambda item: item[0])
    merged: list[tuple[datetime, datetime]] = [intervals[0]]

    for start, end in intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))

    total_days = sum((end - start).days for start, end in merged)
    return round(total_days / 365.25, 2)


def _resume_body_is_empty(parsed: ExtractedResume) -> bool:
    """Structured output may validate while returning no resume sections."""
    return (
        not parsed.professional_experience
        and not parsed.education
        and not (parsed.skills.technical_skills or parsed.skills.soft_skills)
    )


async def _extract_with_structured_output(llm, raw_text: str) -> ExtractedResume:
    structured = llm.with_structured_output(ExtractedResume)
    prompt = EXTRACTION_PROMPT.format(resume_text=raw_text)
    result = await structured.ainvoke(prompt)
    parsed = parse_extracted_resume(result)
    if _resume_body_is_empty(parsed):
        raise ValueError("structured output returned empty resume sections")
    return parsed


async def _extract_with_json_fallback(llm, raw_text: str) -> ExtractedResume:
    """Fallback for Bedrock/OpenAI when structured output returns malformed types."""
    from llm_usage import get_usage

    prompt = EXTRACTION_PROMPT.format(resume_text=raw_text)
    response = await llm.ainvoke(prompt)
    usage = get_usage()
    if usage is not None:
        usage.add_response(response)
    content = getattr(response, "content", str(response))
    if isinstance(content, list):
        content = " ".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    payload = extract_json_from_text(str(content))
    return parse_extracted_resume(payload)


def _backfill_contact_fields(parsed: ExtractedResume, raw_text: str) -> ExtractedResume:
    personal = parsed.personal_info.model_copy()
    changed = False
    if not normalize_email(personal.email):
        emails = extract_emails_from_text(raw_text)
        if emails:
            personal.email = normalize_email(emails[0])
            changed = True
    if not personal.phone:
        phones = extract_phones_from_text(raw_text)
        if phones:
            personal.phone = phones[0]
            changed = True
    if not changed:
        return parsed
    return ExtractedResume(
        personal_info=personal,
        professional_experience=list(parsed.professional_experience),
        education=list(parsed.education),
        skills=parsed.skills,
    )


async def extract_resume_data(raw_text: str, db: AsyncSession) -> ExtractedResume:
    """Run extraction with structured output, falling back to raw JSON parsing."""
    settings = await get_effective_settings(db)
    llm = build_llm_from_settings(settings)
    cleaned_text = clean_resume_text(raw_text)

    if settings.llm_provider == "aws_bedrock":
        provider_label = f"AWS Bedrock ({settings.bedrock_model_id})"
    elif settings.llm_provider == "google":
        provider_label = f"Google AI ({settings.google_model})"
    else:
        provider_label = f"OpenAI ({settings.openai_model})"

    if should_use_chunked_extraction(cleaned_text):
        return await extract_resume_data_chunked(cleaned_text, db)

    errors: list[str] = []
    prefer_json = settings.llm_provider == "aws_bedrock"

    if not prefer_json:
        try:
            parsed = await _extract_with_structured_output(llm, cleaned_text)
            return _backfill_contact_fields(parsed, cleaned_text)
        except (ValidationError, ValueError, TypeError) as exc:
            errors.append(f"structured: {exc}")

    try:
        parsed = await _extract_with_json_fallback(llm, cleaned_text)
        return _backfill_contact_fields(parsed, cleaned_text)
    except (ValidationError, ValueError, json.JSONDecodeError, TypeError) as exc:
        errors.append(f"json fallback: {exc}")
        raise RuntimeError(
            f"LLM extraction failed using {provider_label}. "
            + " | ".join(errors)
        ) from exc


def build_extraction_graph(db: AsyncSession):
    """Build a graph bound to the current DB session for settings-aware LLM calls."""

    async def llm_extraction_node(state: GraphState) -> GraphState:
        try:
            parsed = await extract_resume_data(state["raw_text"], db)
        except Exception as exc:
            settings = await get_effective_settings(db)
            provider_label = f"{settings.llm_provider} ({get_active_model_name(settings)})"
            raise RuntimeError(
                f"LLM extraction failed using {provider_label}: {exc}"
            ) from exc

        return {**state, "parsed_json": parsed}

    def business_logic_node(state: GraphState) -> GraphState:
        parsed = state.get("parsed_json")
        if not parsed:
            return {
                **state,
                "calculated_metrics": CalculatedMetrics(total_years_of_experience=0.0),
            }

        total_years = _calculate_total_years(parsed.professional_experience)
        return {
            **state,
            "calculated_metrics": CalculatedMetrics(
                total_years_of_experience=total_years
            ),
        }

    workflow = StateGraph(GraphState)
    workflow.add_node("llm_extraction", llm_extraction_node)
    workflow.add_node("business_logic", business_logic_node)
    workflow.set_entry_point("llm_extraction")
    workflow.add_edge("llm_extraction", "business_logic")
    workflow.add_edge("business_logic", END)
    return workflow.compile()


async def run_extraction_pipeline(raw_text: str, db: AsyncSession) -> GraphState:
    """Execute the full LangGraph pipeline for a resume's raw text."""
    from llm_usage import reset_usage

    reset_usage()
    graph = build_extraction_graph(db)
    initial_state: GraphState = {
        "raw_text": raw_text,
        "parsed_json": None,
        "calculated_metrics": None,
    }
    return await graph.ainvoke(initial_state)
