"""Gemini text/vision helpers with model ladder + optional OpenRouter fallback."""

from __future__ import annotations

import logging
from typing import Any

from jarvis.config import settings
from jarvis.core.model_ladder import ladder
from jarvis.core.openrouter import openrouter

log = logging.getLogger("jarvis.gemini")


def _client():
    from google import genai

    key = settings.gemini_key
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    return genai.Client(api_key=key)


def generate_text(
    prompt: str,
    *,
    system: str = "",
    module: str | None = None,
    prefer_openrouter: bool = False,
) -> str:
    """Generate text — OpenRouter for selected modules when available, else Gemini ladder."""
    if prefer_openrouter or (module and module in settings.get("openrouter_modules", [])):
        if openrouter.available:
            try:
                return openrouter.complete(prompt, system=system, module=module)
            except Exception as exc:
                log.warning("OpenRouter failed (%s), falling back to Gemini", exc)

    client = _client()

    def _call(model: str) -> str:
        contents = prompt
        config: dict[str, Any] = {}
        if system:
            config["system_instruction"] = system
        resp = client.models.generate_content(model=model, contents=contents, config=config or None)
        return getattr(resp, "text", None) or str(resp)

    return ladder.call(_call)


def generate_with_image(prompt: str, image_bytes: bytes, mime: str = "image/png") -> str:
    from google.genai import types

    client = _client()

    def _call(model: str) -> str:
        part = types.Part.from_bytes(data=image_bytes, mime_type=mime)
        resp = client.models.generate_content(model=model, contents=[prompt, part])
        return getattr(resp, "text", None) or str(resp)

    return ladder.call(_call)
