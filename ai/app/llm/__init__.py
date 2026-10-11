from __future__ import annotations

import httpx

from ..config import Settings, settings as default_settings
from ..models import ModelSpec
from .claude import ClaudeClient
from .gemini import GeminiClient


def make_client(spec: ModelSpec, http: httpx.AsyncClient, s: Settings = default_settings):
    if spec.provider == "gemini":
        return GeminiClient(spec.id, s.gemini_api_key, http)
    return ClaudeClient(spec.id, s.anthropic_api_key, http)
