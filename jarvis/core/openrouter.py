"""OpenRouter client — free-tier models for selected action modules."""

from __future__ import annotations

import json
from typing import Any

import httpx

from jarvis.config import settings


class OpenRouterClient:
    BASE = "https://openrouter.ai/api/v1"

    def __init__(self) -> None:
        self.api_key = settings.openrouter_key
        self.model = settings.get("openrouter_model", "google/gemma-2-9b-it:free")

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.4,
        max_tokens: int = 2048,
        module: str | None = None,
    ) -> str:
        if not self.available:
            raise RuntimeError("OPENROUTER_API_KEY not set")

        if module and module not in settings.get("openrouter_modules", []):
            raise RuntimeError(f"Module {module} is not routed through OpenRouter")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://jarvis.local",
            "X-Title": "JARVIS",
        }
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        with httpx.Client(timeout=60.0) as client:
            r = client.post(f"{self.BASE}/chat/completions", headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
        return data["choices"][0]["message"]["content"]

    def complete(self, prompt: str, *, system: str = "", module: str | None = None) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, module=module)

    def json_complete(self, prompt: str, *, system: str = "", module: str | None = None) -> Any:
        text = self.complete(prompt + "\n\nRespond with valid JSON only.", system=system, module=module)
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)


openrouter = OpenRouterClient()
