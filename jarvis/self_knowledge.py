"""Runtime self-knowledge — generated live each session from OS + plugins."""

from __future__ import annotations

import platform
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from jarvis import __version__
from jarvis.config import ROOT, settings

if TYPE_CHECKING:
    from jarvis.skills.base import SkillRegistry


def build_self_knowledge(registry: SkillRegistry | None = None) -> str:
    name = settings.get("assistant_name", "JARVIS")
    user = settings.get("user_name") or "the user"
    os_name = platform.system()
    os_rel = platform.release()
    machine = platform.machine()
    py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    abilities: list[str] = [
        "Real-time voice conversation via Gemini Live",
        "Push-to-talk (Ctrl+Space) and local wake-word listening",
        "Launch apps, manage files, run terminal commands",
        "Autonomous multi-step task planning",
        "Persistent recallable memory with on-demand search",
        "Web search (news / research / price / compare)",
        "Weather, hardware telemetry, reminders",
        "Browser and desktop control",
        "File analysis (PDF, code, images)",
        "Clipboard intelligence",
        "Morning briefing and proactive check-ins",
        "Google Calendar controls",
        "Undo for file and settings changes",
        "Confirmation required for shutdown / restart / WiFi",
    ]

    limits: list[str] = [
        "Cannot confirm own irreversible actions (shutdown, restart, WiFi)",
        "Does not stream microphone audio while asleep",
        "Never answers its own last spoken sentence (echo guard)",
        "Requires GEMINI_API_KEY; OpenRouter is optional for tool LLM calls",
        "Camera / screen vision only when explicitly requested or enabled",
    ]

    skills_block = ""
    if registry is not None:
        skill_names = sorted(registry.names())
        skills_block = "\nLoaded skills/plugins:\n" + "\n".join(f"- {s}" for s in skill_names)
        for s in skill_names:
            if s not in abilities:
                abilities.append(f"Skill: {s}")

    plugin_dir = ROOT / "plugins"
    plugins = sorted(p.stem for p in plugin_dir.glob("*.py") if not p.name.startswith("_"))
    plugin_block = ""
    if plugins:
        plugin_block = "\nUser plugins:\n" + "\n".join(f"- {p}" for p in plugins)

    return f"""You are {name}, a personal AI assistant running as a desktop app.
Version: {__version__}
User: {user}
Host: {os_name} {os_rel} ({machine}), Python {py}
Working directory root: {ROOT}

Abilities:
{chr(10).join(f"- {a}" for a in abilities)}

Limits:
{chr(10).join(f"- {l}" for l in limits)}
{skills_block}{plugin_block}

Speak naturally. Prefer short spoken replies. Use tools for actions.
Detect and remember the user's spoken language; adapt future replies to it.
When starting a long task, give an instant short acknowledgment in the user's language.
"""


def system_fingerprint() -> dict:
    return {
        "assistant_name": settings.get("assistant_name"),
        "os": platform.system(),
        "os_release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "root": str(ROOT),
        "version": __version__,
    }
