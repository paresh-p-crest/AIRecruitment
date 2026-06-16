"""Load, persist, and mask application settings (LLM provider + credentials)."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import AppSettings
from schemas import SettingsPublic, SettingsTestRequest, SettingsUpdate

load_dotenv()

DEFAULT_BEDROCK_MODEL = "anthropic.claude-3-sonnet-20240229-v1:0"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
from google_models import DEFAULT_GOOGLE_MODEL, normalize_google_model
DEFAULT_AWS_REGION = "us-east-1"

_settings_cache: AppSettings | None = None


def mask_secret(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 4:
        return "****"
    return "*" * (len(value) - 4) + value[-4:]


def _env_fallback() -> dict[str, str | None]:
    return {
        "llm_provider": os.getenv("LLM_PROVIDER", "aws_bedrock"),
        "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
        "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
        "aws_session_token": os.getenv("AWS_SESSION_TOKEN"),
        "aws_region": os.getenv("AWS_REGION", DEFAULT_AWS_REGION),
        "bedrock_model_id": os.getenv(
            "BEDROCK_MODEL_ID", DEFAULT_BEDROCK_MODEL
        ),
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "openai_model": os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        "google_api_key": os.getenv("GOOGLE_API_KEY"),
        "google_model": os.getenv("GOOGLE_MODEL", DEFAULT_GOOGLE_MODEL),
    }


def get_active_model_name(row: AppSettings) -> str:
    if row.llm_provider == "aws_bedrock":
        return row.bedrock_model_id
    if row.llm_provider == "openai":
        return row.openai_model
    if row.llm_provider == "google":
        return normalize_google_model(row.google_model)
    return "unknown"


async def ensure_settings_row(db: AsyncSession) -> AppSettings:
    """Create the singleton settings row on first startup."""
    result = await db.execute(select(AppSettings).where(AppSettings.id == 1))
    row = result.scalar_one_or_none()
    if row:
        return row

    env = _env_fallback()
    row = AppSettings(
        id=1,
        llm_provider=env["llm_provider"] or "aws_bedrock",
        aws_access_key_id=env["aws_access_key_id"],
        aws_secret_access_key=env["aws_secret_access_key"],
        aws_session_token=env["aws_session_token"],
        aws_region=env["aws_region"] or DEFAULT_AWS_REGION,
        bedrock_model_id=env["bedrock_model_id"] or DEFAULT_BEDROCK_MODEL,
        openai_api_key=env["openai_api_key"],
        openai_model=env["openai_model"] or DEFAULT_OPENAI_MODEL,
        google_api_key=env["google_api_key"],
        google_model=env["google_model"] or DEFAULT_GOOGLE_MODEL,
    )
    db.add(row)
    await db.flush()
    return row


def invalidate_settings_cache() -> None:
    global _settings_cache
    _settings_cache = None


async def get_settings_row(db: AsyncSession) -> AppSettings:
    global _settings_cache
    if _settings_cache is not None:
        return _settings_cache

    row = await ensure_settings_row(db)
    _settings_cache = row
    return row


def _merge_env(row: AppSettings) -> AppSettings:
    """Fill empty DB fields from .env so local dev still works."""
    row.google_model = normalize_google_model(row.google_model)
    env = _env_fallback()
    if not row.aws_access_key_id and env["aws_access_key_id"]:
        row.aws_access_key_id = env["aws_access_key_id"]
    if not row.aws_secret_access_key and env["aws_secret_access_key"]:
        row.aws_secret_access_key = env["aws_secret_access_key"]
    if not row.aws_session_token and env["aws_session_token"]:
        row.aws_session_token = env["aws_session_token"]
    if not row.openai_api_key and env["openai_api_key"]:
        row.openai_api_key = env["openai_api_key"]
    if not row.google_api_key and env["google_api_key"]:
        row.google_api_key = env["google_api_key"]
    return row


def to_public_settings(row: AppSettings) -> SettingsPublic:
    row = _merge_env(row)
    return SettingsPublic(
        llm_provider=row.llm_provider,
        aws_access_key_id=row.aws_access_key_id,
        aws_secret_access_key_masked=mask_secret(row.aws_secret_access_key),
        aws_session_token_masked=mask_secret(row.aws_session_token),
        aws_secret_configured=bool(row.aws_secret_access_key),
        aws_session_token_configured=bool(row.aws_session_token),
        aws_region=row.aws_region,
        bedrock_model_id=row.bedrock_model_id,
        openai_api_key_masked=mask_secret(row.openai_api_key),
        openai_api_key_configured=bool(row.openai_api_key),
        openai_model=row.openai_model,
        google_api_key_masked=mask_secret(row.google_api_key),
        google_api_key_configured=bool(row.google_api_key),
        google_model=row.google_model,
        updated_at=row.updated_at,
    )


async def get_public_settings(db: AsyncSession) -> SettingsPublic:
    row = await get_settings_row(db)
    return to_public_settings(row)


async def update_settings(db: AsyncSession, payload: SettingsUpdate) -> SettingsPublic:
    row = await ensure_settings_row(db)
    row = _merge_env(row)
    merged = merge_settings_for_test(
        row,
        SettingsTestRequest(**payload.model_dump()),
    )
    validate_provider_config(merged)

    row.llm_provider = payload.llm_provider
    row.aws_region = payload.aws_region
    row.bedrock_model_id = payload.bedrock_model_id
    row.openai_model = payload.openai_model
    row.google_model = payload.google_model

    if payload.aws_access_key_id is not None:
        row.aws_access_key_id = payload.aws_access_key_id or None

    if payload.aws_secret_access_key:
        row.aws_secret_access_key = payload.aws_secret_access_key

    if payload.aws_session_token is not None:
        row.aws_session_token = payload.aws_session_token or None

    if payload.openai_api_key:
        row.openai_api_key = payload.openai_api_key

    if payload.google_api_key:
        row.google_api_key = payload.google_api_key

    row.updated_at = datetime.now(timezone.utc)
    await db.flush()
    global _settings_cache
    _settings_cache = row
    return to_public_settings(row)


async def get_effective_settings(db: AsyncSession) -> AppSettings:
    row = await get_settings_row(db)
    return _merge_env(row)


def merge_settings_for_test(
    saved: AppSettings, draft: SettingsTestRequest
) -> AppSettings:
    """
    Build ephemeral settings for the provider tab being tested.

    Uses draft form values when provided; otherwise keeps saved credentials so
    other providers stay configured while a different one remains in use.
    """
    saved = _merge_env(saved)
    merged = AppSettings(
        id=saved.id,
        llm_provider=draft.llm_provider,
        aws_access_key_id=(
            draft.aws_access_key_id
            if draft.aws_access_key_id is not None
            else saved.aws_access_key_id
        ),
        aws_secret_access_key=(
            draft.aws_secret_access_key
            if draft.aws_secret_access_key
            else saved.aws_secret_access_key
        ),
        aws_session_token=(
            draft.aws_session_token
            if draft.aws_session_token is not None
            else saved.aws_session_token
        ),
        aws_region=draft.aws_region or saved.aws_region,
        bedrock_model_id=draft.bedrock_model_id or saved.bedrock_model_id,
        openai_api_key=(
            draft.openai_api_key if draft.openai_api_key else saved.openai_api_key
        ),
        openai_model=draft.openai_model or saved.openai_model,
        google_api_key=(
            draft.google_api_key if draft.google_api_key else saved.google_api_key
        ),
        google_model=normalize_google_model(
            draft.google_model or saved.google_model
        ),
        updated_at=saved.updated_at,
    )
    return _merge_env(merged)


def validate_provider_config(row: AppSettings) -> None:
    if row.llm_provider == "aws_bedrock":
        if not row.aws_access_key_id or not row.aws_secret_access_key:
            raise ValueError(
                "AWS Bedrock is selected but Access Key ID or Secret Access Key "
                "is missing. Configure credentials on the Settings page."
            )
        return

    if row.llm_provider == "openai":
        if not row.openai_api_key:
            raise ValueError(
                "OpenAI is selected but API key is missing. "
                "Configure it on the Settings page."
            )
        return

    if row.llm_provider == "google":
        if not row.google_api_key:
            raise ValueError(
                "Google AI Studio is selected but API key is missing. "
                "Configure GOOGLE_API_KEY on the Settings page."
            )
        return

    raise ValueError(f"Unsupported LLM provider: {row.llm_provider}")
