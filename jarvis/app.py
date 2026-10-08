"""Application orchestration — wires HUD, live engine, audio, skills, proactive."""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox

from jarvis.agent.confirm import confirm_gate
from jarvis.agent.undo import undo_stack
from jarvis.audio.devices import audio_io
from jarvis.audio.echo_guard import echo_guard
from jarvis.audio.ptt import PushToTalk
from jarvis.audio.wake_word import WakeWordDetector
from jarvis.audio.waveform import waveform
from jarvis.config import DATA, settings
from jarvis.core.acknowledgment import acknowledger
from jarvis.core.context import context
from jarvis.core.live_engine import LiveEngine
from jarvis.memory.store import memory
from jarvis.proactive.checkins import ProactiveEngine
from jarvis.proactive.hardware_watch import HardwareWatch
from jarvis.proactive.monitoring import TopicMonitor
from jarvis.proactive.morning import build_morning_briefing
from jarvis.remote.dashboard import RemoteDashboard
from jarvis.self_knowledge import build_self_knowledge
from jarvis.skills.base import discover_skills
from jarvis.system.autostart import set_autostart
from jarvis.system.clipboard import ClipboardWatcher
from jarvis.ui.assets import app_icon
from jarvis.ui.clipboard_panel import ClipboardPanel
from jarvis.ui.confirm_dialog import ConfirmDialog
from jarvis.ui.hud import HUD
from jarvis.ui.splash import SplashScreen

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("jarvis")


class JarvisApp:
    def __init__(self) -> None:
        self.qapp = QApplication(sys.argv)
        self.qapp.setApplicationName(settings.get("assistant_name", "JARVIS"))
        self.qapp.setWindowIcon(app_icon())
        self.registry = discover_skills()
        self.splash = SplashScreen()
        self.hud = HUD()
        self.hud.hide()
        self.clipboard_panel = ClipboardPanel()
        self.clipboard_panel.closed.connect(self.clipboard_panel.hide)
        self.ptt_open = False
        self._last_activity = time.time()
        self._morning_done = (DATA / "morning_done.flag")

        # Live engine
        self.engine = LiveEngine(
            on_transcript=self._on_transcript,
            on_audio_out=self._on_audio_out,
            on_state=self._on_engine_state,
            tool_handler=self._tool_handler,
            tool_decls=self.registry.declarations(),
            get_system_prompt=self._system_prompt,
        )
        acknowledger.set_speaker(lambda t: self.engine.speak_local_ack(t))

        # Audio
        mic = settings.get("mic_device")
        spk = settings.get("speaker_device")
        audio_io.set_devices(mic, spk)
        audio_io.start_input(self._on_mic)

        # Wake + PTT
        self.wake = WakeWordDetector(
            phrase=settings.get("wake_word", "hey jarvis"),
            on_wake=self._on_wake,
            auto_sleep_seconds=float(settings.get("auto_sleep_seconds", 120)),
        )
        self.wake.enabled = bool(settings.get("wake_word_enabled", True))
        self.ptt = PushToTalk(on_down=self._ptt_down, on_up=self._ptt_up)
        self.ptt.start()

        # HUD signals
        self.hud.text_submitted.connect(self._on_text)
        self.hud.settings_changed.connect(self._on_settings)
        self.hud.file_dropped.connect(self._on_file_drop)
        self.hud.undo_requested.connect(lambda: self._notify(undo_stack.undo_last()))
        self.hud.ptt_key.connect(self._ptt_window_key)

        # Confirm gate UI
        confirm_gate.set_ui(self._show_confirm)

        # Clipboard
        self.clip_watch = ClipboardWatcher(on_text=self._on_clipboard)
        self.clip_watch.start()

        # Remote
        self.remote = RemoteDashboard(on_text=self._on_text)
        try:
            qr = self.remote.start()
            log.info("Remote QR: %s", qr)
        except Exception as exc:
            log.warning("Remote dashboard failed: %s", exc)

        # Proactive
        self.proactive = ProactiveEngine(speak=lambda t: self.engine.push_text(f"[Proactive] {t}"))
        self.topics = TopicMonitor(alert=lambda t: self.engine.push_text(f"[Alert] {t}"))
        self.hw_watch = HardwareWatch(alert=lambda t: self.engine.push_text(f"[Hardware] {t}"))

        self.tick = QTimer()
        self.tick.timeout.connect(self._tick)
        self.tick.start(2000)

        # Restore session continuity
        context.restore_latest()
        if settings.get("auto_start"):
            set_autostart(True)

        if not settings.gemini_key:
            QMessageBox.warning(
                self.hud,
                "API key missing",
                "Set GEMINI_API_KEY in a .env file (see .env.example).",
            )

    def _system_prompt(self) -> str:
        mem = memory.prompt_slice()
        lang = context.state.language or settings.get("language") or ""
        lang_line = f"\nUser language: {lang}\n" if lang else "\nDetect spoken language and remember it silently.\n"
        return build_self_knowledge(self.registry) + lang_line + (
            f"\nKnown facts (partial — search memory for more):\n{mem}\n" if mem else ""
        )

    def run(self) -> int:
        self.splash.finished.connect(self._after_splash)
        self.splash.show_and_fade(2000)
        return self.qapp.exec()

    def _after_splash(self) -> None:
        self.hud.show()
        self.engine.start()
        self.hud.set_status("asleep")
        QTimer.singleShot(1500, self._maybe_morning)

    # --- events --------------------------------------------------------------
    def _on_mic(self, pcm: bytes) -> None:
        waveform.feed(pcm, "mic" if (self.ptt_open or not self.engine.asleep) else "idle")
        # wake word local energy while asleep — never stream to cloud while asleep
        if self.engine.asleep:
            self.wake.feed_pcm(pcm)
            self.wake.check_energy_wake()
            return
        if echo_guard.should_drop(pcm):
            return
        # PTT mode: only send while held; if wake-open, send continuously until auto-sleep
        if self.ptt_open or not self.engine.asleep:
            self.engine.push_pcm16(pcm)
            self.wake.note_activity()
            self._last_activity = time.time()

    def _on_audio_out(self, pcm: bytes) -> None:
        waveform.feed(pcm, "assistant")
        audio_io.play_pcm16(pcm)
        self.hud.face.feed_assistant_audio(pcm)
        echo_guard.remember_assistant(pcm, self.engine.last_assistant_text)

    def _on_transcript(self, role: str, text: str) -> None:
        if role == "user" and echo_guard.should_drop(b"", transcript_tail=text):
            return
        if role == "user" and self.engine.asleep:
            # local wake from any local ASR path if present
            if self.wake.feed_text(text):
                return
        self.hud.append_transcript(role, text)
        if role == "assistant":
            self.hud.face.set_transcript(text)
            echo_guard.remember_assistant(self.engine.last_assistant_audio, text)
        if role == "user":
            self._detect_language(text)
            self.wake.note_activity()
            # extract memories lightly
            self._maybe_remember(text)

    def _on_engine_state(self, state: str) -> None:
        self.hud.set_status(state)

    def _on_text(self, text: str) -> None:
        self.engine.wake()
        self.engine.push_text(text)
        self.wake.note_activity()

    def _on_wake(self) -> None:
        self.engine.wake()
        self.hud.set_status("listening")
        self._last_activity = time.time()

    def _ptt_down(self) -> None:
        self.ptt_open = True
        self.engine.wake()
        self.hud.set_status("listening")
        self.hud.ptt_hint.setText("PTT OPEN")

    def _ptt_up(self) -> None:
        self.ptt_open = False
        self.hud.ptt_hint.setText("Ctrl+Space")

    def _ptt_window_key(self, key: str, mods: set, down: bool) -> None:
        # window-scoped fallback (non-Windows or when global fails)
        self.ptt.handle_key("space" if "space" in key.lower() or key == str(32) else key, mods, down)

    def _on_settings(self, payload: dict) -> None:
        audio_io.set_devices(payload.get("mic_device"), payload.get("speaker_device"))
        context.on_device_change(mic=payload.get("mic_device"), speaker=payload.get("speaker_device"))
        if payload.get("voice"):
            self.engine.set_voice(payload["voice"])
        self.wake.enabled = bool(payload.get("wake_word_enabled", True))
        set_autostart(bool(payload.get("auto_start", False)))

    def _on_file_drop(self, path: str) -> None:
        self.engine.wake()
        result = self.registry.call("file_analyze", {"path": path, "question": "Analyze and summarize this file."})
        body = result.get("answer") or result
        self.hud.show_content(Path(path).name, body)
        self.engine.push_text(f"I dropped a file for analysis: {path}. Result: {body}")

    def _on_clipboard(self, text: str) -> None:
        # show floating panel — don't steal focus aggressively
        self.clipboard_panel.set_clipboard_text(text)

    def _show_confirm(self, pending) -> None:  # noqa: ANN001
        dlg = ConfirmDialog(pending.description, self.hud)
        self.hud.set_status("confirm")

        def decided(ok: bool) -> None:
            if ok:
                confirm_gate.approve()
            else:
                confirm_gate.deny()

        dlg.decided.connect(decided)
        dlg.open()

    def _tool_handler(self, name: str, args: dict):
        log.info("Tool %s %s", name, args)
        result = self.registry.call(name, args)
        # push displayable results into content panel
        if isinstance(result, dict) and result.get("display") is not None:
            self.hud.show_content(name, result["display"])
        elif isinstance(result, dict) and result.get("result") is not None and name == "web_search":
            self.hud.show_content("Search", result.get("result"))
        if name in {"open_url", "play_video"} and isinstance(result, dict):
            url = result.get("url") or args.get("url")
            if url and ("youtube" in str(url) or str(url).endswith((".mp4", ".webm", ".mkv"))):
                self.hud.play_video(str(url))
        return result

    def _tick(self) -> None:
        if not self.engine.asleep and self.wake.should_auto_sleep() and not self.ptt_open:
            self.engine.sleep()
            self.hud.set_status("asleep")
        self.proactive.tick()
        self.topics.tick()
        self.hw_watch.tick()

    def _maybe_morning(self) -> None:
        today = time.strftime("%Y-%m-%d")
        flag = DATA / "morning_done.flag"
        if flag.exists() and flag.read_text(encoding="utf-8").strip() == today:
            return
        briefing = build_morning_briefing()
        flag.write_text(today, encoding="utf-8")
        self.hud.show_content("Morning briefing", {
            "spoken": briefing["spoken"],
            "news": briefing.get("news"),
            "weather": briefing.get("weather"),
        })
        self.engine.wake()
        self.engine.push_text(
            f"[System] Deliver this morning briefing aloud naturally, then wait:\n{briefing['spoken']}"
        )

    def _detect_language(self, text: str) -> None:
        """Silent language memory — set once from first substantial utterance."""
        if context.state.language or settings.get("language"):
            return
        if len(text.strip()) < 12:
            return
        # Heuristic script detection
        import unicodedata

        scripts = {"LATIN": 0, "CYRILLIC": 0, "GREEK": 0, "ARABIC": 0, "HAN": 0, "HIRAGANA": 0, "DEVANAGARI": 0}
        for ch in text:
            try:
                name = unicodedata.name(ch, "")
            except ValueError:
                continue
            for s in scripts:
                if s in name:
                    scripts[s] += 1
        best = max(scripts, key=scripts.get)
        mapping = {
            "LATIN": "en",
            "CYRILLIC": "ru",
            "GREEK": "el",
            "ARABIC": "ar",
            "HAN": "zh",
            "HIRAGANA": "ja",
            "DEVANAGARI": "hi",
        }
        if scripts[best] > 5:
            lang = mapping.get(best, "en")
            context.state.language = lang
            settings.set("language", lang)
            log.info("Silent language memory → %s", lang)

    def _maybe_remember(self, text: str) -> None:
        lower = text.lower()
        triggers = ("my name is", "i live in", "i prefer", "remember that", "i work on")
        if any(t in lower for t in triggers):
            memory.add(text, category="preference", source="conversation")

    def _notify(self, msg: str) -> None:
        self.hud.append_transcript("assistant", msg)


def run() -> int:
    app = JarvisApp()
    try:
        code = app.run()
    finally:
        # persist session summary for tomorrow morning
        summary = context.end_of_day_summary()
        if summary:
            memory.save_session_summary(summary)
        context.persist()
        app.engine.stop()
        audio_io.stop()
    return code
