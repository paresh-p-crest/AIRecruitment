"""Google AI Studio model ID helpers and deprecated model migration."""

# Deprecated IDs that return 404 on current Gemini API → current replacements
DEPRECATED_GOOGLE_MODELS: dict[str, str] = {
    "gemini-1.5-pro": "gemini-2.5-pro",
    "gemini-1.5-flash": "gemini-2.5-flash",
    "gemini-1.5-flash-8b": "gemini-2.5-flash-lite",
    "gemini-1.5-flash-latest": "gemini-flash-latest",
    "gemini-1.5-flash-lite": "gemini-2.5-flash-lite",
    "gemini-1.5-flash-lite-latest": "gemini-flash-lite-latest",
    "gemini-1.5-pro-latest": "gemini-pro-latest",
    "gemini-pro": "gemini-pro-latest",
}

DEFAULT_GOOGLE_MODEL = "gemini-2.5-flash"

RECOMMENDED_GOOGLE_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview",
    "gemini-3.1-pro-preview",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-pro-latest",
]


def normalize_google_model(model: str | None) -> str:
    """Map retired Gemini model IDs to currently supported ones."""
    if not model or not model.strip():
        return DEFAULT_GOOGLE_MODEL
    cleaned = model.strip()
    return DEPRECATED_GOOGLE_MODELS.get(cleaned, cleaned)
