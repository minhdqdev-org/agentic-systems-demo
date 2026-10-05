"""Environment-backed configuration."""

from __future__ import annotations

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from the environment (and `.env` when present)."""

    # `protected_namespaces=()` because pydantic reserves the `model_` prefix for its own
    # attributes, and `model` is the name that makes the `MODEL` env var obvious.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=(),
    )

    gemini_api_key: SecretStr
    """Read from `GEMINI_API_KEY`. Has no default: a missing key must fail at startup with
    a named field rather than at the first call with an opaque 401."""

    model: str = "gemini-3.5-flash-lite"
    """The one model this chain runs on. Every step uses it -- see the note on per-step
    model routing in the README."""

    temperature_plan: float = 0.4
    """Lower for the outline: it is a structural artifact that gets validated, not prose."""

    temperature_write: float = 0.7
    temperature_polish: float = 0.3

    request_timeout_seconds: float = 120.0


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings singleton."""
    return Settings()  # type: ignore[call-arg]
