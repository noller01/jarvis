"""Proactive 2.0 — time-aware, context-aware check-ins."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Callable

from jarvis.config import settings
from jarvis.core.context import context
from jarvis.memory.store import memory


class ProactiveEngine:
    def __init__(self, speak: Callable[[str], None] | None = None) -> None:
        self.speak = speak
        self._last_checkin = 0.0
        self.interval = 45 * 60  # 45 min

    def tick(self) -> str | None:
        if not settings.get("proactive_enabled", True):
            return None
        now = time.time()
        if now - self._last_checkin < self.interval:
            return None
        # don't interrupt active speech sessions aggressively
        self._last_checkin = now
        hour = datetime.now().hour
        projects = memory.search("project OR working OR deadline", limit=3)
        recent = ""
        if context.state.turns:
            recent = context.state.turns[-1].content[:120]
        if 11 <= hour <= 13:
            msg = "Quick midday check-in — want a short status on your open projects?"
        elif 17 <= hour <= 19:
            msg = "Wrapping up soon? I can summarise what we tackled today."
        elif projects:
            msg = f"Still on your mind: {projects[0].content}. Need anything on that?"
        elif recent:
            msg = "I'm here if you want to continue where we left off."
        else:
            return None
        if self.speak:
            self.speak(msg)
        return msg
