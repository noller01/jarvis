"""Background topic watching — daily headline checks."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable

from jarvis.config import DATA, settings


class TopicMonitor:
    def __init__(self, alert: Callable[[str], None] | None = None) -> None:
        self.alert = alert
        self.path = DATA / "topic_monitor.json"
        self._state = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"last_run": 0, "seen": {}}

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")

    def tick(self) -> list[str]:
        topics = settings.get("background_topics") or []
        if not topics:
            return []
        now = time.time()
        if now - float(self._state.get("last_run") or 0) < 24 * 3600:
            return []
        self._state["last_run"] = now
        alerts = []
        try:
            from duckduckgo_search import DDGS

            with DDGS() as ddgs:
                for topic in topics:
                    rows = list(ddgs.news(topic, max_results=3))
                    for r in rows:
                        key = r.get("url") or r.get("title")
                        if not key or key in self._state["seen"]:
                            continue
                        self._state["seen"][key] = now
                        msg = f"Update on {topic}: {r.get('title')}"
                        alerts.append(msg)
                        if self.alert:
                            self.alert(msg)
        except Exception:
            pass
        # prune seen
        if len(self._state["seen"]) > 500:
            items = sorted(self._state["seen"].items(), key=lambda x: x[1], reverse=True)[:200]
            self._state["seen"] = dict(items)
        self._save()
        return alerts
