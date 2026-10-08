"""Multi-mode web search — Gemini Grounded first, DDG fallback."""

from __future__ import annotations

from typing import Any

from jarvis.core.gemini import generate_text
from jarvis.core.openrouter import openrouter
from jarvis.skills.base import Skill


class WebSearchSkill(Skill):
    name = "web_search"
    TOOL = {
        "name": "web_search",
        "description": "Search the web. Modes: news, research, price, compare, search",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "mode": {
                    "type": "string",
                    "enum": ["news", "research", "price", "compare", "search"],
                },
            },
            "required": ["query"],
        },
    }

    def handler(self, args: dict) -> Any:
        query = args.get("query", "").strip()
        mode = (args.get("mode") or "search").lower()
        if not query:
            return {"ok": False, "error": "empty query"}

        grounded = self._grounded(query, mode)
        if grounded.get("ok"):
            return grounded
        return self._ddg(query, mode)

    def _grounded(self, query: str, mode: str) -> dict:
        try:
            from google import genai
            from google.genai import types
            from jarvis.config import settings

            client = genai.Client(api_key=settings.gemini_key)
            prompt = f"Mode={mode}. Find current information for: {query}. Cite sources."
            # Google Search grounding tool when available
            config = types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )
            resp = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=config,
            )
            text = getattr(resp, "text", None) or str(resp)
            return {"ok": True, "mode": mode, "source": "gemini_grounded", "result": text, "display": text}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _ddg(self, query: str, mode: str) -> dict:
        try:
            from duckduckgo_search import DDGS

            with DDGS() as ddgs:
                if mode == "news":
                    rows = list(ddgs.news(query, max_results=8))
                else:
                    rows = list(ddgs.text(query, max_results=8))
            # optional OpenRouter synthesis
            digest = rows
            try:
                if openrouter.available:
                    digest = openrouter.complete(
                        f"Mode={mode}. Summarise these search results for the user:\n{rows}",
                        module="web_search",
                    )
            except Exception:
                pass
            return {"ok": True, "mode": mode, "source": "ddg", "result": digest, "raw": rows, "display": digest}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
