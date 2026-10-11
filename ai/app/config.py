"""Runtime configuration: environment variables, with an optional ai/.env file."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: Path | None = None) -> None:
    """Tiny .env loader (no extra dependency). Real environment variables win."""
    path = path or Path(__file__).resolve().parent.parent / ".env"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _clean_key(value: str | None) -> str:
    """Treat empty values and .env.example placeholders as 'not configured'."""
    v = (value or "").strip()
    if not v or v.lower().startswith(("your", "changeme", "paste")):
        return ""
    return v


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    tavily_api_key: str = ""
    default_model: str = ""
    backend_url: str = "http://localhost:4000"
    max_steps: int = 8
    tool_timeout_s: float = 20.0
    cors_origins: tuple[str, ...] = ("http://localhost:3000", "http://localhost:4000")

    @classmethod
    def from_env(cls) -> "Settings":
        e = os.environ.get
        return cls(
            gemini_api_key=_clean_key(e("GEMINI_API_KEY")),
            anthropic_api_key=_clean_key(e("ANTHROPIC_API_KEY")),
            tavily_api_key=_clean_key(e("TAVILY_API_KEY")),
            default_model=(e("DEFAULT_MODEL") or "").strip(),
            backend_url=(e("BACKEND_URL") or "http://localhost:4000").rstrip("/"),
            max_steps=max(1, min(int(e("MAX_AGENT_STEPS") or 8), 15)),
            tool_timeout_s=float(e("TOOL_TIMEOUT_S") or 20),
            cors_origins=tuple(
                o.strip()
                for o in (e("CORS_ORIGINS") or "http://localhost:3000,http://localhost:4000").split(",")
                if o.strip()
            ),
        )


load_dotenv()
settings = Settings.from_env()
