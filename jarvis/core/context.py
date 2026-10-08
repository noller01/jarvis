"""Session continuity + sliding-window context compression."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from jarvis.config import DATA, settings
from jarvis.core.openrouter import openrouter


@dataclass
class Turn:
    role: str
    content: str
    ts: float = field(default_factory=time.time)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionState:
    session_id: str
    turns: list[Turn] = field(default_factory=list)
    summary: str = ""
    compressed: list[str] = field(default_factory=list)
    voice: str = ""
    mic_device: Any = None
    speaker_device: Any = None
    language: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class ContextManager:
    """Keeps conversations alive across drops, voice changes, device changes."""

    MAX_TURNS_IN_PROMPT = 40
    COMPRESS_EVERY = 30

    def __init__(self) -> None:
        self.state = SessionState(
            session_id=str(uuid.uuid4()),
            voice=settings.get("voice", "Puck"),
            mic_device=settings.get("mic_device"),
            speaker_device=settings.get("speaker_device"),
            language=settings.get("language", ""),
        )
        self._path = DATA / "sessions" / f"{self.state.session_id}.json"

    def add(self, role: str, content: str, **meta: Any) -> None:
        self.state.turns.append(Turn(role=role, content=content, meta=meta))
        self.state.updated_at = time.time()
        if len(self.state.turns) % self.COMPRESS_EVERY == 0:
            self.compress()
        self.persist()

    def on_device_change(self, *, mic: Any = None, speaker: Any = None) -> None:
        if mic is not None:
            self.state.mic_device = mic
        if speaker is not None:
            self.state.speaker_device = speaker
        self.persist()

    def on_voice_change(self, voice: str) -> None:
        self.state.voice = voice
        settings.set("voice", voice)
        self.persist()

    def prompt_messages(self) -> list[dict[str, str]]:
        msgs: list[dict[str, str]] = []
        if self.state.summary or self.state.compressed:
            blob = self.state.summary
            if self.state.compressed:
                blob = (blob + "\n" if blob else "") + "\n".join(self.state.compressed[-5:])
            msgs.append({"role": "system", "content": f"Earlier conversation summary:\n{blob}"})
        recent = self.state.turns[-self.MAX_TURNS_IN_PROMPT :]
        for t in recent:
            msgs.append({"role": t.role, "content": t.content})
        return msgs

    def compress(self) -> None:
        older = self.state.turns[: -self.MAX_TURNS_IN_PROMPT // 2]
        if not older:
            return
        transcript = "\n".join(f"{t.role}: {t.content}" for t in older[-40:])
        summary = ""
        try:
            if openrouter.available:
                summary = openrouter.complete(
                    f"Compress this conversation into dense bullet facts for future context:\n{transcript}",
                    system="You compress dialogue into lasting facts and open threads.",
                    module="summarize",
                )
            else:
                summary = transcript[-1500:]
        except Exception:
            summary = transcript[-1500:]
        self.state.compressed.append(summary)
        self.state.summary = summary
        # keep recent turns only
        self.state.turns = self.state.turns[-(self.MAX_TURNS_IN_PROMPT) :]

    def persist(self) -> None:
        payload = {
            "session_id": self.state.session_id,
            "summary": self.state.summary,
            "compressed": self.state.compressed,
            "voice": self.state.voice,
            "mic_device": self.state.mic_device,
            "speaker_device": self.state.speaker_device,
            "language": self.state.language,
            "created_at": self.state.created_at,
            "updated_at": self.state.updated_at,
            "turns": [asdict(t) for t in self.state.turns],
        }
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def restore_latest(self) -> bool:
        sessions = sorted((DATA / "sessions").glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not sessions:
            return False
        data = json.loads(sessions[0].read_text(encoding="utf-8"))
        self.state = SessionState(
            session_id=data["session_id"],
            summary=data.get("summary", ""),
            compressed=data.get("compressed", []),
            voice=data.get("voice") or settings.get("voice"),
            mic_device=data.get("mic_device"),
            speaker_device=data.get("speaker_device"),
            language=data.get("language", ""),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            turns=[Turn(**t) for t in data.get("turns", [])],
        )
        self._path = sessions[0]
        return True

    def end_of_day_summary(self) -> str:
        transcript = "\n".join(f"{t.role}: {t.content}" for t in self.state.turns[-60:])
        if not transcript.strip():
            return ""
        try:
            if openrouter.available:
                return openrouter.complete(
                    f"Summarise today's conversation for tomorrow's morning briefing (3-5 sentences):\n{transcript}",
                    module="summarize",
                )
        except Exception:
            pass
        return transcript[:800]


context = ContextManager()
