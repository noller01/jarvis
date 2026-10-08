"""Configuration — loads .env, settings.json, and live preferences."""

from __future__ import annotations

import json
import os
import platform
from copy import deepcopy
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SETTINGS_PATH = DATA / "settings.json"
load_dotenv(ROOT / ".env")

DEFAULTS: dict[str, Any] = {
    "assistant_name": "JARVIS",
    "user_name": "",
    "voice": "Puck",
    "voices": ["Puck", "Charon", "Kore", "Fenrir", "Aoede"],
    "hue": 210,
    "hex_color": "#6B7280",
    "opacity": 0.92,
    "language": "",
    "city": "",
    "mic_device": None,
    "speaker_device": None,
    "wake_word_enabled": True,
    "wake_word": "hey jarvis",
    "auto_sleep_seconds": 120,
    "auto_start": False,
    "theme": {
        "bg": "#0A0A0A",
        "bg_elevated": "#141414",
        "bg_panel": "#1A1A1A",
        "border": "#2A2A2A",
        "text": "#E5E5E5",
        "text_muted": "#9CA3AF",
        "accent": "#6B7280",
        "accent_bright": "#9CA3AF",
        "danger": "#EF4444",
        "success": "#22C55E",
    },
    "gemini_live_model": "gemini-2.5-flash-preview-native-audio-dialog",
    "model_ladder": [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b",
        "gemini-1.5-pro",
        "gemini-2.5-pro",
        "gemini-2.0-pro",
        "gemini-1.0-pro",
    ],
    "openrouter_model": "google/gemma-2-9b-it:free",
    "openrouter_modules": [
        "web_search",
        "memory",
        "flight_finder",
        "desktop_control",
        "file_processor",
        "summarize",
    ],
    "proactive_enabled": True,
    "hardware_alerts": True,
    "background_topics": [],
    "layout": {
        "content_panel": True,
        "memory_panel": False,
        "avatar_scale": 1.0,
    },
}


def _deep_merge(base: dict, overlay: dict) -> dict:
    out = deepcopy(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class Settings:
    def __init__(self) -> None:
        DATA.mkdir(parents=True, exist_ok=True)
        (DATA / "sessions").mkdir(exist_ok=True)
        (DATA / "undo").mkdir(exist_ok=True)
        (DATA / "uploads").mkdir(exist_ok=True)
        self._data = deepcopy(DEFAULTS)
        self.load()
        # env overrides
        if os.getenv("JARVIS_NAME"):
            self._data["assistant_name"] = os.getenv("JARVIS_NAME")
        if os.getenv("USER_NAME"):
            self._data["user_name"] = os.getenv("USER_NAME")
        if os.getenv("CITY"):
            self._data["city"] = os.getenv("CITY")
        if os.getenv("LANGUAGE"):
            self._data["language"] = os.getenv("LANGUAGE")
        if os.getenv("OPENROUTER_MODEL"):
            self._data["openrouter_model"] = os.getenv("OPENROUTER_MODEL")

    def load(self) -> None:
        if SETTINGS_PATH.exists():
            try:
                saved = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
                self._data = _deep_merge(DEFAULTS, saved)
            except Exception:
                pass

    def save(self) -> None:
        SETTINGS_PATH.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any, persist: bool = True) -> None:
        self._data[key] = value
        if persist:
            self.save()

    def update(self, mapping: dict[str, Any], persist: bool = True) -> None:
        self._data.update(mapping)
        if persist:
            self.save()

    @property
    def data(self) -> dict[str, Any]:
        return self._data

    @property
    def gemini_key(self) -> str:
        return os.getenv("GEMINI_API_KEY", "").strip()

    @property
    def openrouter_key(self) -> str:
        return os.getenv("OPENROUTER_API_KEY", "").strip()

    @property
    def platform(self) -> str:
        return platform.system().lower()


settings = Settings()
