"""Skill base + auto-discovery from jarvis/skills and plugins/."""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, Callable

from jarvis.config import ROOT

log = logging.getLogger("jarvis.skills")

ToolDict = dict[str, Any]
Handler = Callable[[dict], Any]


class Skill:
    """Every skill declares TOOL (or TOOLS) + handler."""

    name: str = "skill"
    TOOL: ToolDict | None = None
    TOOLS: list[ToolDict] | None = None

    def handler(self, args: dict) -> Any:
        raise NotImplementedError


class SkillRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}
        self._decls: list[ToolDict] = {}
        self._decls = []
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        tools = []
        if skill.TOOLS:
            tools.extend(skill.TOOLS)
        elif skill.TOOL:
            tools.append(skill.TOOL)
        for tool in tools:
            name = tool.get("name") or skill.name

            def _make(sk: Skill, tool_name: str) -> Handler:
                def _handler(args: dict) -> Any:
                    payload = dict(args or {})
                    payload["_tool"] = tool_name
                    return sk.handler(payload)

                return _handler

            self._handlers[name] = _make(skill, name)
            decl = {
                "name": name,
                "description": tool.get("description", skill.name),
                "parameters": tool.get("parameters")
                or tool.get("parametersJsonSchema")
                or {"type": "object", "properties": {}},
            }
            self._decls.append(decl)
        self._skills[skill.name] = skill
        # allow agent skill to bind registry later
        if hasattr(skill, "bind"):
            try:
                skill.bind(self)
            except Exception:
                pass
        log.info("Registered skill: %s", skill.name)

    def names(self) -> list[str]:
        return list(self._skills.keys())

    def declarations(self) -> list[ToolDict]:
        return list(self._decls)

    def call(self, name: str, args: dict) -> Any:
        if name not in self._handlers:
            return {"ok": False, "error": f"unknown tool: {name}"}
        return self._handlers[name](args or {})


def _load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if not spec or not spec.loader:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


def discover_skills() -> SkillRegistry:
    registry = SkillRegistry()
    skill_dir = Path(__file__).parent
    for path in sorted(skill_dir.glob("*.py")):
        if path.name.startswith("_") or path.name == "base.py":
            continue
        mod_name = f"jarvis.skills.{path.stem}"
        try:
            mod = importlib.import_module(mod_name)
            _register_module(registry, mod)
        except Exception:
            log.exception("Failed loading skill %s", path.name)

    plugin_dir = ROOT / "plugins"
    plugin_dir.mkdir(exist_ok=True)
    # ensure plugins is importable
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    for path in sorted(plugin_dir.glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            mod = _load_module(path, f"jarvis_plugin_{path.stem}")
            if mod:
                _register_module(registry, mod)
        except Exception:
            log.exception("Failed loading plugin %s", path.name)
    return registry


def _register_module(registry: SkillRegistry, mod: Any) -> None:
    # Class-based
    for attr in dir(mod):
        obj = getattr(mod, attr)
        if isinstance(obj, type) and issubclass(obj, Skill) and obj is not Skill:
            registry.register(obj())
    # Module-level TOOL + handler
    if hasattr(mod, "TOOL") and hasattr(mod, "handler"):
        class _Dyn(Skill):
            name = getattr(mod, "NAME", mod.TOOL.get("name", "plugin"))
            TOOL = mod.TOOL

            def handler(self, args: dict) -> Any:
                return mod.handler(args)

        registry.register(_Dyn())
    if hasattr(mod, "TOOLS") and hasattr(mod, "handler"):
        class _DynMulti(Skill):
            name = getattr(mod, "NAME", "plugin")
            TOOLS = mod.TOOLS

            def handler(self, args: dict) -> Any:
                return mod.handler(args)

        registry.register(_DynMulti())
