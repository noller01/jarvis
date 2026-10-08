"""Autonomous multi-step goals."""

from __future__ import annotations

from typing import Any

from jarvis.agent.planner import plan_goal
from jarvis.skills.base import Skill


class AgentSkill(Skill):
    name = "autonomous_tasks"
    TOOL = {
        "name": "autonomous_goal",
        "description": "Plan and execute a complex multi-step goal using available skills",
        "parameters": {
            "type": "object",
            "properties": {"goal": {"type": "string"}},
            "required": ["goal"],
        },
    }

    def __init__(self) -> None:
        self._registry = None

    def bind(self, registry) -> None:  # noqa: ANN001
        self._registry = registry

    def handler(self, args: dict) -> Any:
        goal = args.get("goal", "")
        if not goal:
            return {"ok": False, "error": "empty goal"}
        skills = self._registry.names() if self._registry else []
        steps = plan_goal(goal, skills)
        results = []
        for step in steps:
            tool = step.get("tool")
            step_args = step.get("args") or {}
            if not tool or tool == "none" or not self._registry:
                results.append({"step": step, "result": {"skipped": True}})
                continue
            # prevent recursive autonomous loops
            if tool == "autonomous_goal":
                results.append({"step": step, "result": {"skipped": "no recursion"}})
                continue
            results.append({"step": step, "result": self._registry.call(tool, step_args)})
        return {"ok": True, "plan": steps, "results": results}
