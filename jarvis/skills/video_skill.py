"""Play video on the HUD."""

from __future__ import annotations

from typing import Any

from jarvis.skills.base import Skill


class VideoSkill(Skill):
    name = "video"
    TOOL = {
        "name": "play_video",
        "description": "Play a YouTube URL, local video file, or video URL on the HUD (starts muted)",
        "parameters": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    }

    def handler(self, args: dict) -> Any:
        url = args.get("url") or ""
        if not url:
            return {"ok": False, "error": "no url"}
        return {"ok": True, "url": url, "display": f"Playing {url} (muted)"}
