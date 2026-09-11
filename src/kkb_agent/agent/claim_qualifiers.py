"""Small deterministic vocabulary for explicit financial claim qualifiers.

These checks do not infer titles, units, dates or causality from free prose.
Identifiers use exact workspace/result/value names or explicit ID fields.
Unrecognised prose is outside this vocabulary, not a proof of its meaning.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date

from kkb_agent.core import AnalyticalResult, ResultValue, Scale


def _fold(text: str) -> str:
    return text.lower().replace("\u0307", "").replace("ı", "i")


SCALE_WORDS = {
    "bin": Scale.THOUSAND,
    "milyon": Scale.MILLION,
    "milyar": Scale.BILLION,
    "thousand": Scale.THOUSAND,
    "million": Scale.MILLION,
    "billion": Scale.BILLION,
}
SCALE = re.compile(r"\s*(" + "|".join(SCALE_WORDS) + r")(?:u|ı|ü|i)?\b", re.I)
UNITS = {
    "tl": "try",
    "try": "try",
    "₺": "try",
    "türk lirasi": "try",
    "$": "usd",
    "dolar": "usd",
    "usd": "usd",
    "dollars": "usd",
    "€": "eur",
    "euro": "eur",
    "eur": "eur",
    "£": "gbp",
    "gbp": "gbp",
    "jpy": "jpy",
    "chf": "chf",
    "cad": "cad",
    "aud": "aud",
    "cny": "cny",
    "rub": "rub",
    "sar": "sar",
    "aed": "aed",
    "%": "percent",
    "yüzde": "percent",
    "percent": "percent",
    "percentage points": "percentage_points",
    "yüzde puan": "percentage_points",
    "baz puan": "basis_points",
    "basis points": "basis_points",
    "index points": "index_points",
    "endeks puan": "index_points",
}
_UNIT_TEXT = "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))
UNIT = re.compile(r"(?<!\w)(" + _UNIT_TEXT + r")(?!\w)", re.I)
YEAR = re.compile(r"(?<!\w)(?:19|20)\d{2}(?!\w)")
ISO_DATE = re.compile(r"(?<!\w)\d{4}-\d{2}-\d{2}(?!\w)")
MONTHS = {
    _fold(name): month
    for month, names in enumerate(
        (
            "ocak january",
            "şubat february",
            "mart march",
            "nisan april",
            "mayıs may",
            "haziran june",
            "temmuz july",
            "ağustos august",
            "eylül september",
            "ekim october",
            "kasım november",
            "aralık december",
        ),
        1,
    )
    for name in names.split()
}
MONTH = re.compile(r"\b(" + "|".join(MONTHS) + r")\b", re.I)
CLAUSE_BREAK = re.compile(r";|(?<!\d),|,(?!\d)")
EXPLICIT_ID = re.compile(
    r"\b(series_id|result_id|value_label)\s*=\s*[`\"']?([\w.:-]+?)(?=[`\"']?(?:\s|,|;|$|:\s))",
    re.I,
)
HEADER_ID = re.compile(r"^\s*[`\"']?([\w.:-]+?)[`\"']?:\s")
#: Wording that asserts one thing moves another, which DEC-120 forbids an
#: answer to say. Still a bounded vocabulary: an unlisted causative verb
#: ("artırdı", "affected") is not caught, and nothing here parses prose.
#: Matched on folded text, so case and dotted/dotless i do not matter. A
#: sentence that denies a cause in these words is withheld as well; the
#: result's limitations already say it, and negation handling is how an
#: assertion would slip through. "nedensellik", "nedensel" and "causation"
#: are deliberately absent: they mostly appear in exactly those denials.
CAUSAL_PHRASES = (
    # The cause verbs and nouns, in every tense and hedge.
    r"caus(?:e|es|ed|ing)",
    r"neden\s+ol\w*",
    r"sebep\s+ol\w*",
    r"sebebiyet\s+ver\w*",
    r"yol\s+aç\w*",
    r"neden(?:i|ler)\w*",
    r"sebe(?:bi|pler)\w*",
    # Granger's causal vocabulary. Granger results say "precedes" instead.
    r"granger[\s-]+(?:caus|nedensel)\w*",
    # Attributions: a movement explained by something else.
    r"due\s+to",
    r"because\s+of",
    r"driven\s+by",
    r"le(?:d|ads?|ading)\s+to",
    r"yüzünden",
)
CAUSAL = re.compile(r"\b(?:" + "|".join(CAUSAL_PHRASES) + r")\b", re.I)


def causal_fault(text: str) -> str | None:
    if CAUSAL.search(_fold(text)):
        # Even ResultKind.CAUSALITY is association-only under DEC-120.
        return "Unsupported causal assertion: numeric/association results do not establish cause"
    return None


def amount_qualifiers(text: str, start: int, end: int) -> tuple[Scale | None, tuple[str, ...]]:
    """Only attached qualifiers; never borrow the next number's scale or unit."""
    suffix = text[end:]
    scale_match = SCALE.match(suffix)
    scale = SCALE_WORDS[_fold(scale_match[1])] if scale_match else None
    unit_tail = suffix[scale_match.end() :] if scale_match else suffix
    units = []
    for match in UNIT.finditer(text[:start]):
        if not text[match.end() : start].strip():
            units.append(UNITS[_fold(match[1])])
    trailing = UNIT.match(unit_tail.lstrip())
    if trailing:
        units.append(UNITS[_fold(trailing[1])])
    return scale, tuple(units)


def has_amount_context(text: str, start: int, end: int) -> bool:
    scale, units = amount_qualifiers(text, start, end)
    return scale is not None or bool(units)


def is_date_token(text: str, start: int, end: int) -> bool:
    for match in ISO_DATE.finditer(text):
        if match.start() <= start and end <= match.end():
            try:
                date.fromisoformat(match[0])
            except ValueError:
                return False
            return not has_amount_context(text, match.start(), match.end())
    return False


def clause_context(sentence: str, position: int) -> tuple[str, str]:
    """Local clause plus preceding context; punctuation never splits decimals."""
    start, end = 0, len(sentence)
    for match in CLAUSE_BREAK.finditer(sentence):
        if match.start() >= position:
            end = match.start()
            break
        start = match.end()
    return sentence[start:end], sentence[:start]


def identity_fault(
    clause: str,
    prefix: str,
    name: str,
    result: AnalyticalResult,
    value: ResultValue,
    named: Mapping[str, AnalyticalResult],
) -> str | None:
    aliases = {name, result.result_id, value.label}
    known = {n for n in named} | {r.result_id for r in named.values()}
    known.update(v.label for r in named.values() for v in r.values)
    # An ID-only header before a comma scopes the following clause. Do not
    # inherit a previous financial claim's identity into another column.
    if prefix and not re.search(r"\d", YEAR.sub("", prefix)):
        clause = prefix + clause
    fields = {"series_id": value.label, "result_id": result.result_id, "value_label": value.label}
    for match in EXPLICIT_ID.finditer(clause):
        if match[2] != fields[_fold(match[1])]:
            return f"Explicit {match[1]} {match[2]!r} conflicts with this result/value identity"
    header = HEADER_ID.match(clause)
    if header and header[1] not in aliases:
        # Calendar headers are period qualifiers, not result IDs.
        if not any(pattern.fullmatch(header[1]) for pattern in (ISO_DATE, YEAR, MONTH)):
            return f"Explicit identity {header[1]!r} does not identify this result/value"
    for alias in known:
        if alias not in aliases and re.search(
            r"(?<![\w:])" + re.escape(alias) + r"(?![\w:])", clause
        ):
            return f"Explicit identity {alias!r} conflicts with this result/value identity"
    return None


def period_fault(clause: str, prefix: str, value: ResultValue) -> str | None:
    # A leading date may scope several columns. An explicit local date takes
    # precedence, so a later column cannot borrow another column's month.
    context = clause
    if not YEAR.search(context) and not MONTH.search(context) and not ISO_DATE.search(context):
        context = prefix
    dates = list(ISO_DATE.finditer(context))
    years = [
        m
        for m in YEAR.finditer(context)
        if not has_amount_context(context, m.start(), m.end())
        and not any(d.start() <= m.start() < d.end() for d in dates)
    ]
    months = list(MONTH.finditer(context))
    if not dates and not years and not months:
        return None
    period = value.period
    if period is None:
        return "Explicit period cannot be supported: the result never established a period"
    fault = (
        f"Claim is attributed to {context.strip()!r} but its period is {period.start}..{period.end}"
    )
    for match in dates:
        try:
            written = date.fromisoformat(match[0])
        except ValueError:
            return fault
        if not period.start <= written <= period.end:
            return fault
    if any(not period.start.year <= int(m[0]) <= period.end.year for m in years):
        return fault
    for match in months:
        month = MONTHS[_fold(match[1])]
        following = YEAR.match(context[match.end() :].lstrip())
        candidate_years = (
            [int(following[0])]
            if following
            else list(range(period.start.year, period.end.year + 1))
        )
        if not any(
            (period.start.year, period.start.month)
            <= (year, month)
            <= (period.end.year, period.end.month)
            for year in candidate_years
        ):
            return fault
    return None


def unit_fault(text: str, start: int, end: int, value: ResultValue) -> str | None:
    _, units = amount_qualifiers(text, start, end)
    actual = UNITS.get(_fold(value.unit or ""), _fold(value.unit or ""))
    if any(unit != actual for unit in units):
        return f"Explicit unit/currency {units!r} conflicts with recorded unit {value.unit!r}"
    return None
