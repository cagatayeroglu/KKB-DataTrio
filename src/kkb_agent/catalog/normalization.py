"""Shared search representation for M13-03 / DEC-116, not canonical source text.

This module prepares strings only. It neither indexes nor queries a catalog and
does not generate embedding prompts. Callers retain original CatalogRecord text
and source IDs alongside this deliberately lossy representation. A normalized
match is never proof of series identity, financial meaning or alias equivalence.
"""

import unicodedata
from functools import cache, lru_cache

_SEARCH_I = str.maketrans({"I": "i", "İ": "i", "ı": "i"})


# Each character's answer never changes, and a catalogue repeats the same few hundred
# characters millions of times. Asked afresh per character, `unicodedata.name` alone
# made the knowledge page's first list after a restart take 27 s for 9,090 entries,
# past the web client's 12 s, and the page showed "Analiz tamamlanamadı" (live
# 2026-09-23). The rules are unchanged; each character is looked up once.
@cache
def _combining(char: str) -> bool:
    return bool(unicodedata.combining(char))


@cache
def _latin(char: str) -> bool:
    return unicodedata.name(char, "").startswith("LATIN ")


@cache
def _punctuation(char: str) -> bool:
    """Punctuation that becomes a word boundary: not a dash, percent or slash."""
    category = unicodedata.category(char)
    return category.startswith("P") and category != "Pd" and char not in "%/"


def normalize_search_text(text: str) -> str:
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
    # Every rule acts inside a run of non-space characters - a mark joins the letter
    # before it, a separator sits between two digits - so each word is folded on its
    # own, and a catalogue says the same words thousands of times.
    return " ".join(folded for word in text.split() if (folded := _word(word)))


@lru_cache(maxsize=262_144)
def _word(text: str) -> str:
    folded = unicodedata.normalize("NFC", text).translate(_SEARCH_I).casefold()
    letters: list[str] = []
    latin_base = False
    for char in unicodedata.normalize("NFD", folded):
        if _combining(char):
            if not latin_base:
                letters.append(char)
        else:
            latin_base = _latin(char)
            letters.append(char)
    folded = unicodedata.normalize("NFC", "".join(letters))

    words: list[str] = []
    last = len(folded) - 1
    for index, char in enumerate(folded):
        if _punctuation(char):
            numeric_separator = (
                char in ".,"
                and 0 < index < last
                and folded[index - 1].isdecimal()
                and folded[index + 1].isdecimal()
            )
            words.append(char if numeric_separator else " ")
        else:
            words.append(char)
    return " ".join("".join(words).split())


# Both future preparation entry points are the same callable, not parallel
# implementations that can silently drift. No retrieval stage exists here.
normalize_index_text = normalize_search_text
normalize_query_text = normalize_search_text
