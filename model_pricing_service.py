"""Model token pricing and cost estimation for uploads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ModelPricingSettings

CostDisplayMode = Literal["usd", "credits"]

DEFAULT_CREDITS_PER_USD = 1000.0

# Default USD per 1M tokens (demo estimates — editable in Settings)
DEFAULT_MODEL_PRICING: list[dict[str, Any]] = [
    {
        "model_id": "gpt-4o-mini",
        "provider": "openai",
        "label": "OpenAI gpt-4o-mini",
        "input_per_million_usd": 0.15,
        "output_per_million_usd": 0.60,
    },
    {
        "model_id": "gpt-4o",
        "provider": "openai",
        "label": "OpenAI gpt-4o",
        "input_per_million_usd": 2.50,
        "output_per_million_usd": 10.00,
    },
    {
        "model_id": "gemini-2.5-flash",
        "provider": "google",
        "label": "Google Gemini 2.5 Flash",
        "input_per_million_usd": 0.075,
        "output_per_million_usd": 0.30,
    },
    {
        "model_id": "gemini-2.5-pro",
        "provider": "google",
        "label": "Google Gemini 2.5 Pro",
        "input_per_million_usd": 1.25,
        "output_per_million_usd": 5.00,
    },
    {
        "model_id": "anthropic.claude-3-sonnet-20240229-v1:0",
        "provider": "aws_bedrock",
        "label": "Claude 3 Sonnet (Bedrock)",
        "input_per_million_usd": 3.00,
        "output_per_million_usd": 15.00,
    },
    {
        "model_id": "anthropic.claude-3-haiku-20240307-v1:0",
        "provider": "aws_bedrock",
        "label": "Claude 3 Haiku (Bedrock)",
        "input_per_million_usd": 0.25,
        "output_per_million_usd": 1.25,
    },
    {
        "model_id": "anthropic.claude-3-5-sonnet-20240620-v1:0",
        "provider": "aws_bedrock",
        "label": "Claude 3.5 Sonnet (Bedrock)",
        "input_per_million_usd": 3.00,
        "output_per_million_usd": 15.00,
    },
]


def _normalize_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "model_id": str(entry.get("model_id", "")),
        "provider": str(entry.get("provider", "")),
        "label": str(entry.get("label") or entry.get("model_id", "")),
        "input_per_million_usd": float(entry.get("input_per_million_usd", 0)),
        "output_per_million_usd": float(entry.get("output_per_million_usd", 0)),
    }


def find_pricing_entry(
    pricing: list[dict[str, Any]], model_id: str
) -> dict[str, Any] | None:
    model_id = model_id.strip()
    for entry in pricing:
        if entry.get("model_id") == model_id:
            return entry
    for entry in pricing:
        mid = entry.get("model_id", "")
        if mid and (mid in model_id or model_id in mid):
            return entry
    return None


def estimate_cost(
    *,
    model_id: str,
    input_tokens: int | None,
    output_tokens: int | None,
    total_tokens: int | None,
    pricing: list[dict[str, Any]],
    credits_per_usd: float = DEFAULT_CREDITS_PER_USD,
) -> dict[str, float | None]:
    inp = input_tokens or 0
    out = output_tokens or 0
    if inp == 0 and out == 0 and total_tokens:
        inp = int(total_tokens * 0.75)
        out = total_tokens - inp

    if inp == 0 and out == 0:
        return {"estimated_cost_usd": None, "estimated_cost_credits": None}

    entry = find_pricing_entry(pricing, model_id)
    if not entry:
        return {"estimated_cost_usd": None, "estimated_cost_credits": None}

    usd = (inp / 1_000_000) * entry["input_per_million_usd"] + (
        out / 1_000_000
    ) * entry["output_per_million_usd"]
    credits = usd * credits_per_usd if credits_per_usd > 0 else None
    return {
        "estimated_cost_usd": round(usd, 6),
        "estimated_cost_credits": round(credits, 2) if credits is not None else None,
    }


async def ensure_pricing_settings(db: AsyncSession) -> ModelPricingSettings:
    result = await db.execute(
        select(ModelPricingSettings).where(ModelPricingSettings.id == 1)
    )
    row = result.scalar_one_or_none()
    if row:
        return row
    row = ModelPricingSettings(
        id=1,
        cost_display_mode="usd",
        credits_per_usd=DEFAULT_CREDITS_PER_USD,
        model_pricing=[_normalize_entry(e) for e in DEFAULT_MODEL_PRICING],
    )
    db.add(row)
    await db.flush()
    return row


async def get_pricing_public(db: AsyncSession) -> dict[str, Any]:
    row = await ensure_pricing_settings(db)
    return {
        "cost_display_mode": row.cost_display_mode,
        "credits_per_usd": row.credits_per_usd,
        "model_pricing": row.model_pricing or [],
        "updated_at": row.updated_at,
    }


async def update_pricing_settings(
    db: AsyncSession,
    *,
    cost_display_mode: CostDisplayMode,
    credits_per_usd: float,
    model_pricing: list[dict[str, Any]],
) -> dict[str, Any]:
    row = await ensure_pricing_settings(db)
    row.cost_display_mode = cost_display_mode
    row.credits_per_usd = max(credits_per_usd, 0.01)
    row.model_pricing = [_normalize_entry(e) for e in model_pricing if e.get("model_id")]
    row.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return await get_pricing_public(db)


async def compute_upload_cost(
    db: AsyncSession,
    model_id: str,
    input_tokens: int | None,
    output_tokens: int | None,
    total_tokens: int | None,
) -> dict[str, float | None]:
    pricing_row = await ensure_pricing_settings(db)
    return estimate_cost(
        model_id=model_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        pricing=pricing_row.model_pricing or [],
        credits_per_usd=pricing_row.credits_per_usd,
    )
