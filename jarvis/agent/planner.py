"""Autonomous multi-step goal planning."""

from __future__ import annotations

from typing import Any

from jarvis.core.gemini import generate_text
from jarvis.core.openrouter import openrouter


def plan_goal(goal: str, skills: list[str]) -> list[dict[str, Any]]:
    skill_list = ", ".join(skills)
    prompt = f"""Break this high-level goal into ordered steps.
Goal: {goal}
Available skills/tools: {skill_list}

Return JSON list of objects: [{{"step": 1, "tool": "...", "args": {{}}, "why": "..."}}]
Keep steps minimal and executable."""
    try:
        if openrouter.available:
            data = openrouter.json_complete(prompt, module="desktop_control")
        else:
            import json

            text = generate_text(prompt, system="You are a careful planner. JSON only.")
            text = text.strip().strip("`")
            if text.startswith("json"):
                text = text[4:]
            data = json.loads(text)
        if isinstance(data, dict) and "steps" in data:
            data = data["steps"]
        return list(data)
    except Exception as exc:
        return [{"step": 1, "tool": "none", "args": {}, "why": f"plan_failed: {exc}"}]
