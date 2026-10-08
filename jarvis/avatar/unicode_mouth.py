"""Language-free mouth targets via Unicode letter reduction.

Latin, Cyrillic and Greek collapse to the same articulatory classes.
Scripts that hide pronunciation fall back cleanly to neutral / schwa.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

# Viseme classes used by lip-sync
# X=closed, B=bilabial, F=labiodental, T=dental, S=alveolar spread,
# SH=postalveolar, R=retroflex, O=round, U=tight round, E=spread,
# A=open, W=round glide, M=bilabial nasal, Schwa=neutral


@dataclass
class MouthTarget:
    jaw: float = 0.15       # 0 closed .. 1 open
    lip_spread: float = 0.3 # 0 round .. 1 spread
    lip_round: float = 0.2
    upper_raise: float = 0.0
    lower_push: float = 0.0
    closure: float = 0.0    # hard closure (p/b/m)


# Base letter → class after NFKD + strip combining marks + casefold
_LETTER_CLASS: dict[str, str] = {}

def _reg(letters: str, cls: str) -> None:
    for ch in letters:
        _LETTER_CLASS[ch] = cls

_reg("pbmбпмμπμβ", "B")
_reg("fvфвφ", "F")
_reg("tdnтднτδν", "T")
_reg("szсзςσζ", "S")
_reg("ʃʒшжчщśźčž", "SH")
_reg("rlрлρλ", "R")
_reg("kgqкгκγχ", "T")
_reg("wjwyуюйυ", "W")
_reg("oɔøöоόωө", "O")
_reg("uʊüуυύ", "U")
_reg("eɛéèêëеєэεέηή", "E")
_reg("iɪíìîïиіїыіηιί", "E")
_reg("aɑæáàâäаяάα", "A")
_reg("hх", "Schwa")

# Scripts that typically encode meaning without surface pronunciation
_OPAQUE_SCRIPTS = {
    "HAN", "HANGUL", "HIRAGANA", "KATAKANA", "THAI", "LAO", "MYANMAR",
    "KHMER", "TIBETAN", "ARABIC", "HEBREW", "DEVANAGARI", "BENGALI",
}


def reduce_char(ch: str) -> str:
    if not ch or ch.isspace():
        return " "
    # NFKD strip accents
    decomp = unicodedata.normalize("NFKD", ch)
    base = "".join(c for c in decomp if not unicodedata.combining(c)).casefold()
    if not base:
        return "Schwa"
    c = base[0]
    if c in _LETTER_CLASS:
        return _LETTER_CLASS[c]
    # opaque scripts → schwa fallback
    try:
        name = unicodedata.name(ch, "")
    except ValueError:
        name = ""
    for script in _OPAQUE_SCRIPTS:
        if script in name.replace(" ", "").upper() or script in name.upper():
            return "Schwa"
    cat = unicodedata.category(ch)
    if cat.startswith("P") or cat.startswith("Z"):
        return "X"
    return "Schwa"


_CLASS_TARGET: dict[str, MouthTarget] = {
    "X": MouthTarget(jaw=0.02, lip_spread=0.2, lip_round=0.15, closure=1.0),
    "B": MouthTarget(jaw=0.05, lip_spread=0.15, lip_round=0.1, closure=1.0),
    "M": MouthTarget(jaw=0.05, lip_spread=0.2, lip_round=0.1, closure=0.9),
    "F": MouthTarget(jaw=0.12, lip_spread=0.35, lip_round=0.05, upper_raise=0.4, lower_push=0.3),
    "T": MouthTarget(jaw=0.18, lip_spread=0.4, lip_round=0.1),
    "S": MouthTarget(jaw=0.14, lip_spread=0.75, lip_round=0.05),
    "SH": MouthTarget(jaw=0.16, lip_spread=0.35, lip_round=0.45),
    "R": MouthTarget(jaw=0.2, lip_spread=0.25, lip_round=0.35),
    "O": MouthTarget(jaw=0.45, lip_spread=0.05, lip_round=0.85),
    "U": MouthTarget(jaw=0.25, lip_spread=0.0, lip_round=0.95),
    "E": MouthTarget(jaw=0.28, lip_spread=0.85, lip_round=0.05),
    "A": MouthTarget(jaw=0.72, lip_spread=0.45, lip_round=0.1),
    "W": MouthTarget(jaw=0.22, lip_spread=0.05, lip_round=0.9),
    "Schwa": MouthTarget(jaw=0.22, lip_spread=0.35, lip_round=0.25),
    " ": MouthTarget(jaw=0.08, lip_spread=0.3, lip_round=0.2, closure=0.2),
}


def target_for_class(cls: str) -> MouthTarget:
    return _CLASS_TARGET.get(cls, _CLASS_TARGET["Schwa"])


def targets_from_transcript(text: str) -> list[tuple[str, MouthTarget]]:
    out: list[tuple[str, MouthTarget]] = []
    for ch in text:
        cls = reduce_char(ch)
        out.append((cls, target_for_class(cls)))
    return out
