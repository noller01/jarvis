"""Assistant customization from voice/tools — name, user, voice, colour."""

from __future__ import annotations

from typing import Any

from jarvis.agent.undo import undo_stack
from jarvis.config import settings
from jarvis.skills.base import Skill
from jarvis.ui.theme import apply_hue


class CustomizeSkill(Skill):
    name = "customize"
    TOOL = {
        "name": "customize_assistant",
        "description": "Change assistant name, user name, voice, or colour hue/hex immediately",
        "parameters": {
            "type": "object",
            "properties": {
                "assistant_name": {"type": "string"},
                "user_name": {"type": "string"},
                "voice": {
                    "type": "string",
                    "enum": ["Puck", "Charon", "Kore", "Fenrir", "Aoede"],
                },
                "hue": {"type": "integer"},
                "hex_color": {"type": "string"},
            },
        },
    }

    def handler(self, args: dict) -> Any:
        changed = {}
        for key in ("assistant_name", "user_name", "voice"):
            if args.get(key):
                undo_stack.record_settings(key, settings.get(key), args[key])
                settings.set(key, args[key])
                changed[key] = args[key]
        if args.get("hex_color"):
            from PyQt6.QtGui import QColor

            c = QColor(args["hex_color"])
            if c.isValid():
                hue = c.hue() if c.hue() >= 0 else int(settings.get("hue", 210))
                theme = apply_hue(hue)
                changed["theme"] = theme
        elif args.get("hue") is not None:
            theme = apply_hue(int(args["hue"]))
            changed["theme"] = theme
        return {"ok": True, "changed": changed, "note": "UI applies on next settings sync / restart of panels"}
