"""Supported language models and provider availability."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .config import Settings, settings as default_settings
from .errors import LLMError

_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,79}$")  # goes into a URL path: keep it strict


@dataclass(frozen=True)
class ModelSpec:
    id: str
    provider: str  # "gemini" | "anthropic"
    label: str
    note: str = ""


# Edit this list to add or remove models. Any id starting with "gemini" or "claude" also works
# if you pass it explicitly, which is handy when a newer model ships.
MODELS: tuple[ModelSpec, ...] = (
    ModelSpec("gemini-flash-lite-latest", "gemini", "Gemini Flash Lite (latest)", "Free tier, default"),
    ModelSpec("gemini-flash-latest", "gemini", "Gemini Flash (latest)", "Free tier"),
    ModelSpec("gemini-2.5-flash", "gemini", "Gemini 2.5 Flash", "Free tier, pinned version"),
    ModelSpec("claude-haiku-4-5-20251001", "anthropic", "Claude Haiku 4.5", "Fast and cheap"),
    ModelSpec("claude-sonnet-5-5", "anthropic", "Claude Sonnet 5.5", "Stronger reasoning"),
)


def provider_available(provider: str, s: Settings = default_settings) -> bool:
    if provider == "gemini":
        return bool(s.gemini_api_key)
    if provider == "anthropic":
        return bool(s.anthropic_api_key)
    return False


def list_models(s: Settings = default_settings) -> list[dict]:
    return [
        {
            "id": m.id,
            "provider": m.provider,
            "label": m.label,
            "note": m.note,
            "available": provider_available(m.provider, s),
        }
        for m in MODELS
    ]


def resolve_model(model_id: str | None, s: Settings = default_settings) -> ModelSpec:
    """Pick the model for a run, or raise LLMError with a helpful message."""
    if model_id:
        if not _MODEL_ID.match(model_id):
            raise LLMError("bad_model", "Invalid model id.")
        known = next((m for m in MODELS if m.id == model_id), None)
        if known is None:
            lowered = model_id.lower()
            if lowered.startswith("gemini"):
                known = ModelSpec(model_id, "gemini", model_id)
            elif lowered.startswith("claude"):
                known = ModelSpec(model_id, "anthropic", model_id)
            else:
                raise LLMError("bad_model", f"Unknown model '{model_id}'.")
        if not provider_available(known.provider, s):
            key = "GEMINI_API_KEY" if known.provider == "gemini" else "ANTHROPIC_API_KEY"
            raise LLMError("no_key", f"{known.label} needs {key}. Add it to ai/.env and restart the AI service.")
        return known

    if s.default_model:
        try:
            return resolve_model(s.default_model, s)
        except LLMError:
            pass  # fall through to the first available model
    for m in MODELS:
        if provider_available(m.provider, s):
            return m
    raise LLMError(
        "no_key",
        "No model API key is configured. Add GEMINI_API_KEY (free at aistudio.google.com/apikey) "
        "or ANTHROPIC_API_KEY to ai/.env, then restart the AI service.",
    )
