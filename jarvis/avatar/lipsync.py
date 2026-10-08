"""Real lip-sync — ~50 mouth shapes/sec from formants + transcript."""

from __future__ import annotations

import time
from dataclasses import replace

import numpy as np

from jarvis.avatar.unicode_mouth import MouthTarget, targets_from_transcript, target_for_class


def _formants(pcm: bytes, rate: int = 24000) -> tuple[float, float, float]:
    """Estimate F1/F2/energy from a short PCM window (software LPC-ish)."""
    arr = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
    if arr.size < 128:
        return 0.0, 0.0, 0.0
    # pre-emphasis
    x = arr[1:] - 0.97 * arr[:-1]
    energy = float(np.sqrt(np.mean(x * x)) + 1e-6)
    # autocorrelation LPC order 8
    n = min(len(x), 512)
    x = x[:n] * np.hanning(n)
    r = np.correlate(x, x, mode="full")[n - 1 : n + 9]
    if r[0] <= 0:
        return 500.0, 1500.0, energy
    # Levinson-ish reflection
    a = np.zeros(9)
    a[0] = 1.0
    e = r[0]
    for i in range(1, 9):
        acc = r[i]
        for j in range(1, i):
            acc += a[j] * r[i - j]
        k = -acc / (e + 1e-9)
        a[i] = k
        for j in range(1, i):
            a[j], a[i - j] = a[j] + k * a[i - j], a[i - j]  # rough
        e *= max(1e-6, 1 - k * k)
    # spectral peaks via DFT of LPC impulse response
    impulse = np.zeros(256)
    impulse[0] = 1.0
    # IIR filter approx
    y = np.zeros(256)
    aa = a.copy()
    for t in range(256):
        s = impulse[t] if t == 0 else 0.0
        for j in range(1, min(9, t + 1)):
            s -= aa[j] * y[t - j]
        y[t] = s
    spec = np.abs(np.fft.rfft(y))
    freqs = np.fft.rfftfreq(256, d=1.0 / rate)
    peaks = []
    for i in range(2, len(spec) - 2):
        if spec[i] > spec[i - 1] and spec[i] > spec[i + 1] and freqs[i] > 200:
            peaks.append((spec[i], freqs[i]))
    peaks.sort(reverse=True)
    f1 = peaks[0][1] if peaks else 500.0
    f2 = peaks[1][1] if len(peaks) > 1 else 1500.0
    if f2 < f1:
        f1, f2 = f2, f1
    return float(f1), float(f2), energy


def formant_to_target(f1: float, f2: float, energy: float) -> MouthTarget:
    # Map F1→jaw, F2→spread/round (classic vowel chart)
    jaw = float(np.clip((f1 - 300) / 600.0, 0.05, 0.9))
    spread = float(np.clip((f2 - 800) / 1400.0, 0.0, 1.0))
    roundness = 1.0 - spread
    if energy < 200:
        return MouthTarget(jaw=0.08, lip_spread=0.3, lip_round=0.2, closure=0.4)
    # bilabial-ish low energy bursts
    closure = 1.0 if energy < 400 and jaw < 0.2 else 0.0
    return MouthTarget(
        jaw=jaw,
        lip_spread=spread * 0.9,
        lip_round=roundness * 0.85,
        closure=closure,
    )


class LipSyncEngine:
    """Produces ~50 Hz mouth targets blending formants and transcript."""

    def __init__(self) -> None:
        self.current = MouthTarget()
        self._transcript_targets: list[MouthTarget] = []
        self._ti = 0
        self._last_t = time.time()
        self._fps = 50.0

    def set_transcript(self, text: str) -> None:
        pairs = targets_from_transcript(text)
        self._transcript_targets = [t for _, t in pairs] or [target_for_class("Schwa")]
        self._ti = 0

    def feed_audio(self, pcm: bytes, rate: int = 24000) -> MouthTarget:
        f1, f2, energy = _formants(pcm, rate)
        audio_t = formant_to_target(f1, f2, energy)
        # advance transcript cursor ~50 shapes/sec proportional to audio energy
        now = time.time()
        dt = now - self._last_t
        self._last_t = now
        steps = max(1, int(dt * self._fps)) if energy > 250 else 0
        text_t = self.current
        if self._transcript_targets:
            self._ti = min(self._ti + steps, len(self._transcript_targets) - 1)
            text_t = self._transcript_targets[self._ti]
        # blend: closures/spreads/rounds from both — not a volume meter
        blended = MouthTarget(
            jaw=audio_t.jaw * 0.55 + text_t.jaw * 0.45,
            lip_spread=audio_t.lip_spread * 0.4 + text_t.lip_spread * 0.6,
            lip_round=audio_t.lip_round * 0.45 + text_t.lip_round * 0.55,
            upper_raise=max(audio_t.upper_raise, text_t.upper_raise),
            lower_push=max(audio_t.lower_push, text_t.lower_push),
            closure=max(audio_t.closure, text_t.closure),
        )
        # smooth
        self.current = MouthTarget(
            jaw=self.current.jaw * 0.35 + blended.jaw * 0.65,
            lip_spread=self.current.lip_spread * 0.35 + blended.lip_spread * 0.65,
            lip_round=self.current.lip_round * 0.35 + blended.lip_round * 0.65,
            upper_raise=self.current.upper_raise * 0.4 + blended.upper_raise * 0.6,
            lower_push=self.current.lower_push * 0.4 + blended.lower_push * 0.6,
            closure=self.current.closure * 0.25 + blended.closure * 0.75,
        )
        return self.current

    def idle(self) -> MouthTarget:
        self.current = replace(
            self.current,
            jaw=self.current.jaw * 0.9 + 0.08 * 0.1,
            closure=self.current.closure * 0.8,
            lip_spread=self.current.lip_spread * 0.9 + 0.3 * 0.1,
            lip_round=self.current.lip_round * 0.9 + 0.2 * 0.1,
        )
        return self.current


lipsync = LipSyncEngine()
