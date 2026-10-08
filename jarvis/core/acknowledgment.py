"""Instant context-aware acknowledgment when a longer task starts."""

from __future__ import annotations

import random
from typing import Callable

# Short phrases keyed by rough language family / code
ACKS: dict[str, list[str]] = {
    "en": [
        "On it.",
        "Working on that now.",
        "Give me a moment.",
        "Starting that for you.",
        "Right away.",
    ],
    "nl": ["Ik ga ermee aan de slag.", "Momentje.", "Komt eraan.", "Direct."],
    "de": ["Sofort.", "Einen Moment.", "Ich kümmere mich darum.", "Wird erledigt."],
    "fr": ["Tout de suite.", "Un instant.", "Je m'en occupe.", "C'est parti."],
    "es": ["Ahora mismo.", "Un momento.", "Me ocupo.", "Enseguida."],
    "it": ["Subito.", "Un momento.", "Ci penso io.", "Parto."],
    "pt": ["Agora mesmo.", "Um momento.", "Já trato disso.", "Vou começar."],
    "pl": ["Zaraz.", "Chwileczkę.", "Zajmuję się tym.", "Startuję."],
    "ru": ["Сейчас.", "Минутку.", "Занимаюсь.", "Начинаю."],
    "uk": ["Зараз.", "Хвилинку.", "Беруся за це.", "Починаю."],
    "el": ["Αμέσως.", "Μια στιγμή.", "Το αναλαμβάνω.", "Ξεκινάω."],
    "sv": ["Genast.", "Ett ögonblick.", "Jag tar det.", "Sätter igång."],
    "da": ["Straks.", "Et øjeblik.", "Jeg klarer det.", "Går i gang."],
    "no": ["Med en gang.", "Et øyeblikk.", "Jeg tar det.", "Setter i gang."],
    "fi": ["Heti.", "Hetki.", "Hoidan sen.", "Aloitan."],
    "tr": ["Hemen.", "Bir saniye.", "İlgileniyorum.", "Başlıyorum."],
    "ar": ["حاضر.", "لحظة.", "أبدأ الآن.", "على طول."],
    "zh": ["马上。", "稍等。", "我来处理。", "开始了。"],
    "ja": ["すぐやります。", "少々お待ちを。", "取りかかります。", "了解です。"],
    "ko": ["바로 할게요.", "잠시만요.", "처리하겠습니다.", "시작합니다."],
    "hi": ["ठीक है।", "एक पल।", "कर रहा हूँ।", "शुरू करता हूँ।"],
}


def pick_ack(language: str = "en", task_hint: str = "") -> str:
    lang = (language or "en").split("-")[0].lower()
    pool = ACKS.get(lang) or ACKS["en"]
    phrase = random.choice(pool)
    if task_hint:
        # lightly contextualise without inventing long speech
        short = task_hint.strip()[:40]
        if lang == "en":
            return f"{phrase} {short}." if not phrase.endswith(".") else f"{phrase[:-1]} — {short}."
    return phrase


class InstantAcknowledger:
    def __init__(self, speak: Callable[[str], None] | None = None) -> None:
        self._speak = speak

    def set_speaker(self, speak: Callable[[str], None]) -> None:
        self._speak = speak

    def fire(self, language: str = "en", task_hint: str = "") -> str:
        text = pick_ack(language, task_hint)
        if self._speak:
            try:
                self._speak(text)
            except Exception:
                pass
        return text


acknowledger = InstantAcknowledger()
