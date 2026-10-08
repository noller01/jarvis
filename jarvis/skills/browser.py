"""Browser control — open URLs and basic navigation."""

from __future__ import annotations

import platform
import subprocess
import webbrowser
from typing import Any

from jarvis.skills.base import Skill

SYSTEM = platform.system().lower()


class BrowserSkill(Skill):
    name = "browser"
    TOOLS = [
        {
            "name": "open_url",
            "description": "Open a URL in the default browser",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
        {
            "name": "browser_search",
            "description": "Open a web search in the browser",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
        {
            "name": "browser_new_tab",
            "description": "Open a new browser tab with optional URL",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
            },
        },
    ]

    def handler(self, args: dict) -> Any:
        if "query" in args and "url" not in args:
            q = args["query"].replace(" ", "+")
            url = f"https://www.google.com/search?q={q}"
            webbrowser.open(url)
            return {"ok": True, "url": url}
        url = args.get("url") or "about:blank"
        if not url.startswith("http") and url != "about:blank":
            url = "https://" + url
        webbrowser.open(url, new=2)
        return {"ok": True, "url": url}
