"""Gemini Live engine — ultra-low latency voice + tool calling."""

from __future__ import annotations

import asyncio
import base64
import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from jarvis.config import settings
from jarvis.core.acknowledgment import acknowledger
from jarvis.core.context import context
from jarvis.self_knowledge import build_self_knowledge

log = logging.getLogger("jarvis.live")

# Preferred Live / native-audio models (ladder within live)
LIVE_MODELS = [
    "gemini-2.5-flash-preview-native-audio-dialog",
    "gemini-2.0-flash-live-001",
    "gemini-2.0-flash-exp",
]


class LiveEngine:
    """Bidirectional audio session with Gemini Live + tool dispatch."""

    def __init__(
        self,
        *,
        on_transcript: Callable[[str, str], None] | None = None,
        on_audio_out: Callable[[bytes], None] | None = None,
        on_state: Callable[[str], None] | None = None,
        tool_handler: Callable[[str, dict], Any] | None = None,
        tool_decls: list[dict] | None = None,
        get_system_prompt: Callable[[], str] | None = None,
    ) -> None:
        self.on_transcript = on_transcript
        self.on_audio_out = on_audio_out
        self.on_state = on_state
        self.tool_handler = tool_handler
        self.tool_decls = tool_decls or []
        self.get_system_prompt = get_system_prompt or (lambda: build_self_knowledge())
        self._running = False
        self._asleep = True
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._session = None
        self._send_q: asyncio.Queue | None = None
        self._last_assistant_text = ""
        self._last_assistant_audio: bytes = b""
        self._model_index = 0
        self._connected = False
        self.voice = settings.get("voice", "Puck")

    @property
    def asleep(self) -> bool:
        return self._asleep

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def last_assistant_text(self) -> str:
        return self._last_assistant_text

    @property
    def last_assistant_audio(self) -> bytes:
        return self._last_assistant_audio

    def wake(self) -> None:
        self._asleep = False
        self._set_state("listening")

    def sleep(self) -> None:
        self._asleep = True
        self._set_state("asleep")

    def _set_state(self, state: str) -> None:
        if self.on_state:
            try:
                self.on_state(state)
            except Exception:
                pass

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._thread_main, name="jarvis-live", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._loop and self._send_q:
            try:
                asyncio.run_coroutine_threadsafe(self._send_q.put(None), self._loop)
            except Exception:
                pass

    def set_voice(self, voice: str) -> None:
        self.voice = voice
        context.on_voice_change(voice)
        # reconnect with new voice without wiping context
        if self._running:
            self._request_reconnect()

    def _request_reconnect(self) -> None:
        if self._loop and self._send_q:
            asyncio.run_coroutine_threadsafe(self._send_q.put(("__reconnect__", {})), self._loop)

    def push_pcm16(self, pcm: bytes) -> None:
        """Feed mic PCM (16-bit mono 16kHz). Dropped while asleep."""
        if self._asleep or not self._running or not self._loop or not self._send_q:
            return
        asyncio.run_coroutine_threadsafe(self._send_q.put(("audio", pcm)), self._loop)

    def push_text(self, text: str) -> None:
        if not text.strip() or not self._loop or not self._send_q:
            return
        self._asleep = False
        context.add("user", text)
        asyncio.run_coroutine_threadsafe(self._send_q.put(("text", text)), self._loop)

    def speak_local_ack(self, text: str) -> None:
        """Immediate short reply path (also used by InstantAcknowledger)."""
        if self.on_transcript:
            self.on_transcript("assistant", text)
        # Prefer Live session speak if connected; else TTS fallback via text inject
        if self._loop and self._send_q and self._connected:
            asyncio.run_coroutine_threadsafe(
                self._send_q.put(("speak", text)),
                self._loop,
            )

    def _thread_main(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._run())
        finally:
            self._connected = False
            self._loop.close()

    async def _run(self) -> None:
        while self._running:
            model = LIVE_MODELS[min(self._model_index, len(LIVE_MODELS) - 1)]
            try:
                await self._session_loop(model)
            except Exception as exc:
                log.exception("Live session error: %s", exc)
                self._connected = False
                self._set_state("reconnecting")
                msg = str(exc).lower()
                if any(x in msg for x in ("quota", "429", "unavailable", "404", "not found")):
                    if self._model_index < len(LIVE_MODELS) - 1:
                        self._model_index += 1
                await asyncio.sleep(1.5)

    async def _session_loop(self, model: str) -> None:
        from google import genai
        from google.genai import types

        key = settings.gemini_key
        if not key:
            self._set_state("no_api_key")
            await asyncio.sleep(5)
            return

        client = genai.Client(api_key=key, http_options={"api_version": "v1beta"})
        self._send_q = asyncio.Queue()

        tools = []
        if self.tool_decls:
            tools.append(types.Tool(function_declarations=self.tool_decls))

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self.voice)
                )
            ),
            system_instruction=self.get_system_prompt(),
            tools=tools or None,
            input_audio_transcription={},
            output_audio_transcription={},
        )

        log.info("Connecting Live model=%s voice=%s", model, self.voice)
        self._set_state("connecting")

        async with client.aio.live.connect(model=model, config=config) as session:
            self._session = session
            self._connected = True
            self._set_state("asleep" if self._asleep else "listening")

            # Seed continuity summary without wiping turns
            if context.state.summary:
                try:
                    await session.send_client_content(
                        turns={
                            "role": "user",
                            "parts": [
                                {
                                    "text": (
                                        "[Session continuity — prior summary, do not treat as a new request]\n"
                                        + context.state.summary
                                    )
                                }
                            ],
                        },
                        turn_complete=True,
                    )
                except Exception:
                    pass

            recv_task = asyncio.create_task(self._receive_loop(session))
            try:
                while self._running:
                    item = await self._send_q.get()
                    if item is None:
                        break
                    kind, payload = item
                    if kind == "__reconnect__":
                        break
                    if kind == "audio" and not self._asleep:
                        await session.send_realtime_input(
                            audio=types.Blob(data=payload, mime_type="audio/pcm;rate=16000")
                        )
                    elif kind == "text":
                        self._set_state("thinking")
                        await session.send_client_content(
                            turns={"role": "user", "parts": [{"text": payload}]},
                            turn_complete=True,
                        )
                    elif kind == "speak":
                        await session.send_client_content(
                            turns={
                                "role": "user",
                                "parts": [
                                    {
                                        "text": (
                                            f"[Speak this short acknowledgment aloud now, then continue: {payload}]"
                                        )
                                    }
                                ],
                            },
                            turn_complete=True,
                        )
            finally:
                recv_task.cancel()
                self._connected = False
                try:
                    await recv_task
                except asyncio.CancelledError:
                    pass

    async def _receive_loop(self, session: Any) -> None:
        assistant_buf = []
        audio_buf = bytearray()
        async for msg in session.receive():
            sc = getattr(msg, "server_content", None)
            if sc:
                if getattr(sc, "input_transcription", None) and sc.input_transcription.text:
                    text = sc.input_transcription.text
                    if self.on_transcript:
                        self.on_transcript("user", text)
                if getattr(sc, "output_transcription", None) and sc.output_transcription.text:
                    text = sc.output_transcription.text
                    assistant_buf.append(text)
                    if self.on_transcript:
                        self.on_transcript("assistant_partial", text)
                if sc.model_turn:
                    for part in sc.model_turn.parts or []:
                        inline = getattr(part, "inline_data", None)
                        if inline and inline.data:
                            raw = inline.data
                            if isinstance(raw, str):
                                raw = base64.b64decode(raw)
                            audio_buf.extend(raw)
                            if self.on_audio_out:
                                self.on_audio_out(raw)
                            self._set_state("speaking")
                if sc.turn_complete:
                    full = "".join(assistant_buf).strip()
                    if full:
                        self._last_assistant_text = full
                        context.add("assistant", full)
                        if self.on_transcript:
                            self.on_transcript("assistant", full)
                    if audio_buf:
                        self._last_assistant_audio = bytes(audio_buf)
                    assistant_buf.clear()
                    audio_buf.clear()
                    self._set_state("listening" if not self._asleep else "asleep")

            # tool calls
            tool = getattr(msg, "tool_call", None)
            if tool and tool.function_calls:
                self._set_state("thinking")
                from google.genai import types

                responses = []
                for fc in tool.function_calls:
                    name = fc.name
                    args = dict(fc.args or {})
                    # Instant ack for longer tools
                    acknowledger.fire(
                        language=context.state.language or settings.get("language") or "en",
                        task_hint=name.replace("_", " "),
                    )
                    result: Any = {"ok": False, "error": "no handler"}
                    if self.tool_handler:
                        try:
                            result = self.tool_handler(name, args)
                        except Exception as exc:
                            result = {"ok": False, "error": str(exc)}
                    responses.append(
                        types.FunctionResponse(id=fc.id, name=name, response={"result": result})
                    )
                await session.send_tool_response(function_responses=responses)


# Singleton constructed by app
live_engine: LiveEngine | None = None
