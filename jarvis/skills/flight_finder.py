"""Flight finder — search via web + OpenRouter synthesis."""

from __future__ import annotations

from typing import Any

from jarvis.core.openrouter import openrouter
from jarvis.skills.base import Skill
from jarvis.skills.web_search import WebSearchSkill


class FlightFinderSkill(Skill):
    name = "flight_finder"
    TOOL = {
        "name": "find_flights",
        "description": "Find flights between cities on a date",
        "parameters": {
            "type": "object",
            "properties": {
                "from_city": {"type": "string"},
                "to_city": {"type": "string"},
                "date": {"type": "string"},
            },
            "required": ["from_city", "to_city", "date"],
        },
    }

    def handler(self, args: dict) -> Any:
        q = f"flights from {args.get('from_city')} to {args.get('to_city')} on {args.get('date')} prices"
        search = WebSearchSkill().handler({"query": q, "mode": "price"})
        if openrouter.available and search.get("ok"):
            try:
                summary = openrouter.complete(
                    f"Extract plausible flight options from:\n{search.get('result')}",
                    module="flight_finder",
                )
                return {"ok": True, "flights": summary, "display": summary}
            except Exception:
                pass
        return search
