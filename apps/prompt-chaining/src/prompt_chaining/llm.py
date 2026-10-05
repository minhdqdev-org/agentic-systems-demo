"""Chat-model factory.

This chain calls Google directly. It runs every step on one model, so there is nothing for
an LLM gateway to route between and adding one would be ceremony that obscured the pattern
being taught. The `bifrost-gateway` app is where the gateway lives, for a demo that needs
several providers or per-step model choice.
"""

from __future__ import annotations

from langchain_google_genai import ChatGoogleGenerativeAI

from prompt_chaining.settings import get_settings


def chat_model(*, temperature: float = 0.7, **kwargs) -> ChatGoogleGenerativeAI:
    """Return the chain's chat model at the given temperature."""
    settings = get_settings()
    return ChatGoogleGenerativeAI(
        model=settings.model,
        google_api_key=settings.gemini_api_key,
        temperature=temperature,
        timeout=settings.request_timeout_seconds,
        **kwargs,
    )
