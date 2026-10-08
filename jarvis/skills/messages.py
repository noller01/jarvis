"""Send messages via WhatsApp / Telegram deep links."""

from __future__ import annotations

import urllib.parse
import webbrowser
from typing import Any

from jarvis.skills.base import Skill


class MessagesSkill(Skill):
    name = "send_message"
    TOOL = {
        "name": "send_message",
        "description": "Compose a message via WhatsApp, Telegram, or mailto",
        "parameters": {
            "type": "object",
            "properties": {
                "channel": {"type": "string", "enum": ["whatsapp", "telegram", "email"]},
                "to": {"type": "string", "description": "Phone with country code, username, or email"},
                "text": {"type": "string"},
            },
            "required": ["channel", "text"],
        },
    }

    def handler(self, args: dict) -> Any:
        channel = (args.get("channel") or "whatsapp").lower()
        text = args.get("text") or ""
        to = args.get("to") or ""
        if channel == "whatsapp":
            phone = "".join(c for c in to if c.isdigit())
            url = f"https://wa.me/{phone}?text={urllib.parse.quote(text)}"
        elif channel == "telegram":
            if to.startswith("@"):
                to = to[1:]
            url = f"https://t.me/{to}?text={urllib.parse.quote(text)}" if to else f"https://t.me/share/url?text={urllib.parse.quote(text)}"
        else:
            url = f"mailto:{to}?body={urllib.parse.quote(text)}"
        webbrowser.open(url)
        return {"ok": True, "opened": url, "note": "User must press send in the app"}
