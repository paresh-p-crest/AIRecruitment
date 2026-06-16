"""Build LangChain chat models from persisted application settings."""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from sqlalchemy.ext.asyncio import AsyncSession

from models import AppSettings
from settings_service import validate_provider_config


def build_llm_from_settings(settings: AppSettings) -> BaseChatModel:
    validate_provider_config(settings)

    if settings.llm_provider == "aws_bedrock":
        from langchain_aws import ChatBedrockConverse

        kwargs: dict = {
            "model": settings.bedrock_model_id,
            "region_name": settings.aws_region,
            "temperature": 0,
            "aws_access_key_id": settings.aws_access_key_id,
            "aws_secret_access_key": settings.aws_secret_access_key,
        }
        if settings.aws_session_token:
            kwargs["aws_session_token"] = settings.aws_session_token

        return ChatBedrockConverse(**kwargs)

    if settings.llm_provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.openai_model,
            temperature=0,
            api_key=settings.openai_api_key,
        )

    if settings.llm_provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        from google_models import normalize_google_model

        return ChatGoogleGenerativeAI(
            model=normalize_google_model(settings.google_model),
            temperature=0,
            google_api_key=settings.google_api_key,
        )

    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")


async def get_structured_llm(db: AsyncSession, schema):
    from settings_service import get_effective_settings

    settings = await get_effective_settings(db)
    llm = build_llm_from_settings(settings)
    return llm.with_structured_output(schema), settings
