"""Shared search representation for M13-03 / DEC-116, not canonical source text.

This module prepares strings only. It neither indexes nor queries a catalog and
does not generate embedding prompts. Callers retain original CatalogRecord text
and source IDs alongside this deliberately lossy representation. A normalized
match is never proof of series identity, financial meaning or alias equivalence.
"""

import unicodedata

_SEARCH_I = str.maketrans({"I": "i", "İ": "i", "ı": "i"})


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

    folded = unicodedata.normalize("NFC", text).translate(_SEARCH_I).casefold()
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


# Both future preparation entry points are the same callable, not parallel
# implementations that can silently drift. No retrieval stage exists here.
normalize_index_text = normalize_search_text
normalize_query_text = normalize_search_text
