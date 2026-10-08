"""Audio device picker — OS-visible devices, measured for actual I/O."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

log = logging.getLogger("jarvis.audio.devices")

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"


@dataclass
class AudioDevice:
    index: int
    name: str
    kind: str  # input | output
    channels: int
    default_samplerate: float
    measured_ok: bool = False


def _sd():
    import sounddevice as sd

    return sd


def list_devices(measure: bool = True) -> list[AudioDevice]:
    sd = _sd()
    host = sd.query_devices()
    out: list[AudioDevice] = []
    for i, d in enumerate(host):
        name = d.get("name") or f"Device {i}"
        # Filter to short OS-facing list: skip unused null devices
        if d["max_input_channels"] > 0:
            out.append(
                AudioDevice(
                    index=i,
                    name=name,
                    kind="input",
                    channels=int(d["max_input_channels"]),
                    default_samplerate=float(d.get("default_samplerate") or SAMPLE_RATE),
                )
            )
        if d["max_output_channels"] > 0:
            out.append(
                AudioDevice(
                    index=i,
                    name=name,
                    kind="output",
                    channels=int(d["max_output_channels"]),
                    default_samplerate=float(d.get("default_samplerate") or SAMPLE_RATE),
                )
            )
    if measure:
        for dev in out:
            dev.measured_ok = _measure(dev)
        out = [d for d in out if d.measured_ok]
    return out


def _measure(dev: AudioDevice) -> bool:
    sd = _sd()
    try:
        if dev.kind == "input":
            rec = sd.rec(
                int(0.05 * SAMPLE_RATE),
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype=DTYPE,
                device=dev.index,
            )
            sd.wait()
            return rec is not None and len(rec) > 0
        else:
            silence = np.zeros(int(0.02 * SAMPLE_RATE), dtype=np.int16)
            sd.play(silence, samplerate=SAMPLE_RATE, device=dev.index)
            sd.wait()
            return True
    except Exception as exc:
        log.debug("Device measure failed %s: %s", dev.name, exc)
        return False


def default_input_index() -> int | None:
    sd = _sd()
    try:
        return int(sd.default.device[0])
    except Exception:
        return None


def default_output_index() -> int | None:
    sd = _sd()
    try:
        return int(sd.default.device[1])
    except Exception:
        return None


class AudioIO:
    """Mic capture + speaker playback with selectable devices."""

    def __init__(self) -> None:
        self.mic_index: int | None = None
        self.speaker_index: int | None = None
        self._in_stream = None
        self._out_stream = None
        self._on_mic: Any = None
        self._playing = False

    def set_devices(self, mic: int | None, speaker: int | None) -> None:
        self.mic_index = mic
        self.speaker_index = speaker
        self.restart_streams()

    def start_input(self, on_pcm: Any) -> None:
        self._on_mic = on_pcm
        self.restart_streams()

    def restart_streams(self) -> None:
        self.stop()
        if self._on_mic is None:
            return
        sd = _sd()

        def callback(indata, frames, time_info, status):  # noqa: ANN001
            if status:
                log.debug("input status: %s", status)
            pcm = bytes(indata)
            try:
                self._on_mic(pcm)
            except Exception:
                pass

        self._in_stream = sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=1024,
            device=self.mic_index,
            callback=callback,
        )
        self._in_stream.start()

        self._out_stream = sd.RawOutputStream(
            samplerate=24000,  # Gemini Live typically 24kHz out
            channels=CHANNELS,
            dtype=DTYPE,
            device=self.speaker_index,
        )
        self._out_stream.start()

    def play_pcm16(self, pcm: bytes, rate: int = 24000) -> None:
        if not self._out_stream:
            return
        try:
            self._playing = True
            self._out_stream.write(pcm)
        except Exception as exc:
            log.debug("play error: %s", exc)
        finally:
            self._playing = False

    @property
    def is_playing(self) -> bool:
        return self._playing

    def stop(self) -> None:
        for s in (self._in_stream, self._out_stream):
            if s is not None:
                try:
                    s.stop()
                    s.close()
                except Exception:
                    pass
        self._in_stream = None
        self._out_stream = None


audio_io = AudioIO()
