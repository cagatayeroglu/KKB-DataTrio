"""Folding each word on its own gives exactly what folding the whole text gave.

The knowledge page's first list after a restart spent 22 s of 27 folding 9,090
catalogue texts one character at a time (live 2026-09-23), past the web client's 12 s.
Every rule acts inside a run of non-space characters, so words are folded once and
kept. The reference below is the previous implementation, verbatim, as the oracle.
"""

from __future__ import annotations

import random
import unicodedata

import pytest

from kkb_agent.catalog.normalization import normalize_search_text

_REFERENCE_I = str.maketrans({"I": "i", "İ": "i", "ı": "i"})


def reference(text: str) -> str:
    """Return deterministic search text without locale, I/O or record mutation.

    Rules: canonical Unicode equivalence (NFC), Turkish I variants -> i and
    casefold, Latin diacritic removal (NFD), then NFC again. This folding is only
    for the separate search representation required by ROADMAP; non-Latin text
    and its combining marks are retained, not discarded through ASCII encoding.

    Punctuation becomes a word boundary, except dashes, percent and slash, and
    decimal/grouping dots/commas between digits. Keep those potentially meaningful
    signs rather than interpreting numbers, dates, ratios or negation. Whitespace
    collapses to one space; empty/whitespace-only input returns an empty string.
    None and other non-strings are rejected rather than coerced into search text.
    No stemming, stop-word removal, translation, aliases or semantic inference.
    """
    if not isinstance(text, str):
        raise TypeError("Search text must be a string")

    folded = unicodedata.normalize("NFC", text).translate(_REFERENCE_I).casefold()
    letters: list[str] = []
    latin_base = False
    for char in unicodedata.normalize("NFD", folded):
        if unicodedata.combining(char):
            if not latin_base:
                letters.append(char)
        else:
            latin_base = unicodedata.name(char, "").startswith("LATIN ")
            letters.append(char)
    folded = unicodedata.normalize("NFC", "".join(letters))

    words: list[str] = []
    for index, char in enumerate(folded):
        category = unicodedata.category(char)
        numeric_separator = (
            char in ".,"
            and 0 < index < len(folded) - 1
            and folded[index - 1].isdecimal()
            and folded[index + 1].isdecimal()
        )
        if category.startswith("P") and category != "Pd" and char not in "%/":
            words.append(char if numeric_separator else " ")
        else:
            words.append(char)
    return " ".join("".join(words).split())


EDGE = [
    " ",
    "\t",
    "\n",
    "\x0b",
    "\x1c",
    "\x85",
    "\u00a0",
    "\u1680",
    "\u2000",
    "\u2028",
    "\u3000",
    "\u180e",
    "\u200b",
    "a",
    "I",
    "i",
    "\u0130",
    "\u0131",
    "\u00e7",
    "\u011f",
    "\u015f",
    "\u0301",
    "\u0307",
    "\u0338",
    "\u0345",
    "\u0327",
    "\u03a3",
    "\u03c2",
    "\u212b",
    "\u212a",
    "\u2126",
    "\u1e9e",
    "\u00df",
    "\ufb01",
    "\u00b2",
    "\u0416",
    "\u4e2d",
    ".",
    ",",
    ";",
    "%",
    "/",
    "-",
    "\u2013",
    "(",
    "'",
    "\u00ab",
    "0",
    "9",
    "\u0661",
]


@pytest.mark.parametrize(
    "text",
    [
        "Tüketici Kredileri - Taşıt (milyon TL), 1.234,5 %3,2",
        "İSTANBUL ıĞdır I\u0307ZMİR",
        "e\u0301 \u0301a K\u212a \u03a3\u03c3\u03c2",
        "1.2.3 ,5 5, .5 5.",
        "",
        "  \t\u3000 ",
    ],
)
def test_known_texts_fold_as_before(text):
    assert normalize_search_text(text) == reference(text)


def test_random_texts_fold_as_before():
    rng = random.Random(23)
    for _ in range(20_000):
        text = "".join(rng.choice(EDGE) for _ in range(rng.randint(0, 30)))
        assert normalize_search_text(text) == reference(text), repr(text)
