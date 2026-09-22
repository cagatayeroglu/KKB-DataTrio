"""Small deterministic vocabulary for explicit financial claim qualifiers.

These checks do not infer titles, units, dates or causality from free prose.
Identifiers use exact workspace/result/value names or explicit ID fields.
Unrecognised prose is outside this vocabulary, not a proof of its meaning.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import date

from kkb_agent.core import DIMENSIONLESS, AnalyticalResult, ResultValue, Scale


def fold(text: str) -> str:
    """Case and the dotted/dotless i, removed: the vocabularies match on this."""
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
    # analytics.change records point changes under these singular names.
    "percentage point": "percentage_points",
    "index point": "index_points",
    "yüzde puan": "percentage_points",
    # Turkish inflects the phrase, and the longest spelling wins only if it is spelled
    # here: "yüzde puanlık" could not match "yüzde puan" (a letter follows it), so the
    # matcher fell back to "yüzde" and read percent. The writer had used exactly the
    # right words and the gate withheld the sentence for a unit conflict with itself
    # (live 2026-09-22: "-0,0620 yüzde puanlık hareket").
    "yüzde puanlık": "percentage_points",
    "yüzde puanlik": "percentage_points",
    "yüzde puanı": "percentage_points",
    "yüzde puana": "percentage_points",
    "baz puan": "basis_points",
    "baz puanlık": "basis_points",
    "baz puanlik": "basis_points",
    "basis points": "basis_points",
    "index points": "index_points",
    "endeks puan": "index_points",
    # A number of things. The label says what they are, so the display adds no unit
    # word; these spellings exist so a sentence that names them still binds.
    "kişi": "count",
    "adet": "count",
    "işlem": "count",
    "count": "count",
    # A mass, which a precious-metal series is quoted in. Without these a sentence
    # naming the unit could not bind to the value it described. (Taken from PR #316.)
    "kg": "kg",
    "kilogram": "kg",
    "gram": "g",
    "gr": "g",
    "g": "g",
    "ton": "t",
    "t": "t",
    # A quoted price is money per quantity (DEC-177), in both spellings a reader
    # uses. Series with these units had no display at all (finding DN-6.4).
    **{
        spelling: f"{currency.lower()}/{quantity}"
        for currency, money in (
            ("TRY", ("tl", "try")),
            ("USD", ("usd", "dolar")),
            ("EUR", ("eur", "euro")),
        )
        for quantity, words in (
            ("g", ("gr", "gram", "g")),
            ("kg", ("kg",)),
            ("oz", ("ons", "oz")),
            ("t", ("ton", "t")),
            ("piece", ("adet",)),
        )
        for spelling in (f"{word}/{unit}" for word in money for unit in words)
    },
}
_UNIT_TEXT = "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))
UNIT = re.compile(r"(?<!\w)(" + _UNIT_TEXT + r")(?!\w)", re.I)
YEAR = re.compile(r"(?<!\w)(?:19|20)\d{2}(?!\w)")
ISO_DATE = re.compile(r"(?<!\w)\d{4}-\d{2}-\d{2}(?!\w)")
#: A year-month such as 2025-12 (for example a price reference month). Its digits are
#: a calendar token, never a quantity; it is not a period qualifier by itself.
YEAR_MONTH = re.compile(r"(?<![\w-])(?:19|20)\d{2}-(?:0[1-9]|1[0-2])(?![\w-])")
#: The period display this system itself writes, e.g. 2021-02-01..2021-02-28.
DATE_RANGE = re.compile(r"\d{4}-\d{2}-\d{2}\.\.\d{4}-\d{2}-\d{2}")
MONTHS = {
    fold(name): month
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
#: A date as a person writes it: "5 Ocak 2024", "26 Aralık", "1 Şubat 2025 haftası". The
#: day is not a figure, and neither is the year. Live 2026-09-22: "5 Ocak 2024 haftasında
#: ... 42,1" lost its whole sentence because 5 matched no value of the result, and with it
#: the one number the sentence was written to report.
WRITTEN_DATE = re.compile(
    r"(?<![\d.,])(?:[12]\d|3[01]|0?[1-9])\s+(?:" + "|".join(MONTHS) + r")"
    r"(?:\s+(?:19|20)\d{2})?(?![\d.,])",
    re.I,
)
CLAUSE_BREAK = re.compile(r";|(?<!\d),|,(?!\d)")
EXPLICIT_ID = re.compile(
    r"\b(series_id|result_id|value_label)\s*=\s*[`\"']?([\w.:-]+?)(?=[`\"']?(?:\s|,|;|$|:\s))",
    re.I,
)
HEADER_ID = re.compile(r"^\s*[`\"']?([\w.:-]+?)[`\"']?:\s")
IDENTIFIER_SHAPE = re.compile(r"[_.:\d-]")
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
    # Direct or hedged influence verbs observed in ordinary analyst prose.
    # "arttı" (rose) is not "artırdı" (made rise); keep that distinction.
    r"artir\w*",
    r"azalt\w*",
    r"tetikle\w*",
    r"etkile\w*",
    r"baskila\w*",
    r"affect\w*",
    r"contribut\w*",
)
CAUSAL = re.compile(r"\b(?:" + "|".join(CAUSAL_PHRASES) + r")\b", re.I)


#: Wording that says values, data or results do not exist or cannot be computed.
#: The gate cannot prove an absence, and a computed result shown beside the
#: answer contradicts one (the M11-07 live Turn 3 said an added column had no
#: values). Bounded folded vocabulary, not a parser: "geçiş yok" or "dışlanan
#: dönem bulunmuyor" describe counts and are deliberately not listed.
ABSENCE_PHRASES = (
    r"(?:değer|veri|gözlem|sonuç)\w*\s+eksik\b",
    r"(?:değer|veri|sonuç)\w*\s+(?:bulunm(?:uyor|am)\w*|yok\w*|mevcut\s+değil\w*)",
    r"(?:değer|veri|sonuç)\w*\s+(?:yer\s+)?almi(?:yor|yo)\w*",
    r"hesaplanam\w*",
    r"bulunamad\w*",
    r"no\s+(?:values?|data|results?)",
    r"(?:values?|data|results?)\s+(?:is|are)\s+(?:missing|unavailable|not\s+available)",
    r"(?:cannot|could\s+not)\s+be\s+(?:computed|calculated)",
)
ABSENCE = re.compile(r"\b(?:" + "|".join(ABSENCE_PHRASES) + r")", re.I)
GENERIC_MISSING_SAMPLES = re.compile(r"(?:veri|bazi\s+gözlemler)\s+eksik(?:tir)?\.?", re.I)


def absence_fault(text: str, *, missing_samples: bool = False) -> str | None:
    folded = fold(text).strip()
    # A count of missing observations proves generic partial coverage, never
    # that a particular month, source or result is absent.
    if missing_samples and GENERIC_MISSING_SAMPLES.fullmatch(folded):
        return None
    if ABSENCE.search(folded):
        return (
            "Unsupported absence claim: computed results are shown; the gate cannot prove absence"
        )
    return None


def causal_fault(text: str) -> str | None:
    if CAUSAL.search(fold(text)):
        # Even ResultKind.CAUSALITY is association-only under DEC-120.
        return "Unsupported causal assertion: numeric/association results do not establish cause"
    return None


def amount_qualifiers(text: str, start: int, end: int) -> tuple[Scale | None, tuple[str, ...]]:
    """Only attached qualifiers; never borrow the next number's scale or unit."""
    suffix = text[end:]
    scale_match = SCALE.match(suffix)
    scale = SCALE_WORDS[fold(scale_match[1])] if scale_match else None
    unit_tail = suffix[scale_match.end() :] if scale_match else suffix
    units = []
    for match in UNIT.finditer(text[:start]):
        if not text[match.end() : start].strip():
            units.append(UNITS[fold(match[1])])
    trailing = UNIT.match(unit_tail.lstrip())
    if trailing:
        units.append(UNITS[fold(trailing[1])])
    return scale, tuple(units)


#: "2023=100": how an index names its base year. It is part of the series' name, not a
#: figure: neither the year nor the hundred measures anything (live 2026-09-21: a note
#: naming "TCMB Türkiye geneli endeksi (2023=100)" was withheld because 100 is no value).
_BASE_NOTATION = re.compile(r"(?<![\d.,])(?:19|20)\d{2}\s*=\s*100(?![\d.,])")


def is_base_notation(text: str, start: int, end: int) -> bool:
    """Whether the number at [start, end) sits inside an index's base-year notation."""
    return any(
        found.start() <= start and end <= found.end() for found in _BASE_NOTATION.finditer(text)
    )


def has_amount_context(text: str, start: int, end: int) -> bool:
    scale, units = amount_qualifiers(text, start, end)
    return scale is not None or bool(units)


#: A number that enumerates rather than measures: "(1)", a line's leading "2." or
#: "3)". Live 2026-09-20: a reply listing the agent's own tools as "(1) ... (2) ..."
#: had that whole sentence withheld, because those markers bound to nothing, and the
#: answer that reached the reader began mid-thought.
_LIST_MARKER = re.compile(
    "(?:"
    r"(?<=[(])(?P<paren>\d{1,2})(?=[)])"
    "|"
    r"(?:(?<=^)|(?<=\n)|(?<=; )|(?<=: ))(?P<lead>\d{1,2})(?=[).-]\s)"
    ")"
)


def is_list_marker(text: str, start: int, end: int) -> bool:
    """Whether the number at this position enumerates instead of measuring.

    Only a bare one- or two-digit marker, and only where nothing gives it an
    amount: a figure with a unit or a scale word is a claim wherever it sits.
    """
    if has_amount_context(text, start, end):
        return False
    # "(3) milyon TL" is an amount whose scale word sits past the bracket, which
    # the qualifier vocabulary does not read through on its own.
    if text[end : end + 1] == ")" and has_amount_context(text, start, end + 1):
        return False
    for match in _LIST_MARKER.finditer(text):
        group = "paren" if match.group("paren") else "lead"
        if match.start(group) == start and match.end(group) == end:
            return True
    return False


def is_date_token(text: str, start: int, end: int) -> bool:
    for match in YEAR_MONTH.finditer(text):
        if match.start() <= start and end <= match.end():
            return not has_amount_context(text, match.start(), match.end())
    for match in ISO_DATE.finditer(text):
        if match.start() <= start and end <= match.end():
            try:
                date.fromisoformat(match[0])
            except ValueError:
                return False
            return not has_amount_context(text, match.start(), match.end())
    for match in WRITTEN_DATE.finditer(text):
        if match.start() <= start and end <= match.end():
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
        if match[2] != fields[fold(match[1])]:
            return f"Explicit {match[1]} {match[2]!r} conflicts with this result/value identity"
    header = HEADER_ID.match(clause)
    # A plain word before a colon that names nothing known ("Değerlendirme:",
    # "Sonuç:") is a discourse label. Identifier-shaped headers and any known
    # result/value name still must identify this value.
    if (
        header
        and header[1] not in aliases
        and (IDENTIFIER_SHAPE.search(header[1]) or header[1] in known)
    ):
        # Calendar headers are period qualifiers, not result IDs.
        calendar = (ISO_DATE, YEAR, MONTH, DATE_RANGE, YEAR_MONTH)
        if not any(pattern.fullmatch(header[1]) for pattern in calendar):
            return f"Explicit identity {header[1]!r} does not identify this result/value"
    for alias in known:
        if alias not in aliases and re.search(
            r"(?<![\w:])" + re.escape(alias) + r"(?![\w:])", clause
        ):
            return f"Explicit identity {alias!r} conflicts with this result/value identity"
    return None


TABLE_COUNT_LABELS = {
    # Read by a person, not only by the gate. "Koşul altında sürücü yönünü karşılayan dönem
    # sayısı" was the harness's own sentence in every reference answer, and the writer's
    # interpretation took its vocabulary from it (live 2026-09-21). Which series is the
    # first and which the second, and in which direction, is said in the line above them
    # (`presentation.comparison_heading`). No phrase may contain another: the gate tells
    # the counts apart by finding exactly one of them in a sentence.
    "complete monthly transitions": "Karşılaştırılan aydan aya geçiş sayısı",
    "transitions excluded for missing observations": (
        "Eksik gözlem içerdiği için sayılmayan geçiş sayısı"
    ),
    "transitions meeting the condition": "Ön koşulu sağlayan geçiş sayısı",
    "eligible transitions matching the driver direction": (
        "Birinci serinin belirtilen yönde hareket ettiği ay sayısı"
    ),
    "eligible transitions matching the target direction": (
        "İkinci serinin belirtilen yönde hareket ettiği ay sayısı"
    ),
    "eligible transitions matching both directions": (
        "İki hareketin aynı ayda birlikte görüldüğü ay sayısı"
    ),
}


def table_count_display_label(result: AnalyticalResult, value: ResultValue) -> str | None:
    """Return the controlled prose label for the result's final table comparison."""
    if result.evidence is None:
        return None
    comparison_id = next(
        (
            item.parameters.get("comparison_id")
            for item in reversed(result.evidence.transformations)
            if item.operation == "table_co_movement"
        ),
        None,
    )
    if not isinstance(comparison_id, str):
        return None
    prefix = f"table comparison {comparison_id}: "
    if not value.label.startswith(prefix):
        return None
    return TABLE_COUNT_LABELS.get(value.label.removeprefix(prefix))


#: Controlled prose for the four counts a co-movement result publishes. These are
#: what a later comparison inherits, and without a phrase of their own they cannot
#: be named at all once a new comparison contributes an equal count.
COMOVEMENT_COUNT_LABELS = {
    "transitions": "Karşılaştırılan ardışık ay geçişi sayısı",
    "driver_fell": "Birinci serinin düştüğü ay sayısı",
    "target_rose": "Birinci seri düşerken ikinci serinin arttığı ay sayısı",
    "target_did_not_rise": "Birinci seri düşerken ikinci serinin artmadığı ay sayısı",
}


def comovement_count_meaning(label: str) -> str | None:
    """Which of the four co-movement counts a value label carries, if any.

    The shape is the marker: only `analytics.comovement` builds these labels,
    embedding the driver and target labels between fixed words.
    """
    if label == "consecutive monthly transitions compared":
        return "transitions"
    if not label.startswith("transitions where "):
        return None
    if label.endswith(" did not rise"):
        return "target_did_not_rise"
    if label.endswith(" rose"):
        return "target_rose"
    if label.endswith(" fell"):
        return "driver_fell"
    return None


def comovement_count_display_label(result: AnalyticalResult, value: ResultValue) -> str | None:
    """Return the controlled prose label for a co-movement count, inherited or not."""
    if value.unit != DIMENSIONLESS:
        return None
    meaning = comovement_count_meaning(value.label)
    return COMOVEMENT_COUNT_LABELS.get(meaning) if meaning is not None else None


def controlled_count_label(result: AnalyticalResult, value: ResultValue) -> str | None:
    """The one controlled phrase that names this count, from either family."""
    return table_count_display_label(result, value) or comovement_count_display_label(result, value)


def value_meaning(result: AnalyticalResult, value: ResultValue) -> str:
    """What a value measures, for deciding whether two equal figures are one fact.

    A comparison labels each count with its own identity ("table comparison 3f2a...:
    complete monthly transitions"), so two comparisons over one table never share a label
    although both count the same 59 transitions. The controlled role phrase is what the
    count means, and what a sentence can say; any other value means its label.
    """
    return controlled_count_label(result, value) or value.label


def comovement_count_identity_fault(
    clause: str, result: AnalyticalResult, value: ResultValue
) -> str | None:
    """Narrow a count claim to one controlled co-movement meaning.

    The mirror of the table-comparison rule. A comparison built on an earlier
    co-movement retains its four counts, and a new comparison can publish an
    equal number; without this, the inherited count has no wording that binds it
    and the whole sentence is withheld as ambiguous.
    """
    folded = fold(clause)
    selected = [label for label in COMOVEMENT_COUNT_LABELS.values() if fold(label) in folded]
    if not selected:
        return None
    expected = comovement_count_display_label(result, value)
    if len(selected) != 1 or expected != selected[0]:
        return "Explicit co-movement count wording conflicts with this value identity"
    return None


def table_count_identity_fault(
    clause: str, result: AnalyticalResult, value: ResultValue
) -> str | None:
    """Narrow a count claim to one controlled table-comparison meaning.

    A final result can retain an earlier comparison count with the same value,
    unit and coverage. Value-only binding would either reject the supported
    claim as ambiguous or, worse, select the wrong count. A controlled phrase
    identifies one of the six final comparison metrics; unrecognised prose
    continues to receive no semantic privilege.
    """
    folded = fold(clause)
    selected = [label for label in TABLE_COUNT_LABELS.values() if fold(label) in folded]
    if not selected:
        return None
    expected = table_count_display_label(result, value)
    if len(selected) != 1 or expected != selected[0]:
        return "Explicit table-comparison count wording conflicts with this value identity"
    return None


#: Wording that marks a date as a price reference ("2025-12 fiyatlarıyla").
PRICE_REFERENCE = r"(?:['’][^\W\d_]+)?\s*(?:fiyat|price)"


def mask_price_references(text: str, references: Sequence[date]) -> str:
    """Blank a recorded deflation reference month written as a price reference.

    Only the exact recorded month (e.g. 2025-12, Aralık 2025, 2025 Aralık) and
    only before price wording is masked; any other date still qualifies the claim.
    """
    for reference in references:
        names = "|".join(
            name.replace("i", "[iıİI]")
            for name, month in MONTHS.items()
            if month == reference.month
        )
        token = (
            rf"(?:(?<![\w-]){reference.year}-{reference.month:02d}(?![\w-])"
            rf"|(?<!\w)(?:{names})\s+{reference.year}(?!\w)"
            rf"|(?<!\w){reference.year}\s+(?:{names})(?!\w))"
        )
        text = re.sub(
            token + rf"(?={PRICE_REFERENCE})", lambda m: " " * len(m[0]), text, flags=re.I
        )
    return text


def _dated_mentions(context: str) -> list[tuple[int, int]]:
    """Where a clause names a period: a date, a month with its year, or a year alone."""
    spans = [(found.start(), found.end()) for found in ISO_DATE.finditer(context)]
    # "2026-06" is one mention. Read as a year with a stray "-06" after it, the "06" counted
    # as a figure standing after the last date, and a price month nobody recorded paired off.
    spans += [
        (found.start(), found.end())
        for found in YEAR_MONTH.finditer(context)
        if not any(start <= found.start() < end for start, end in spans)
    ]
    for found in MONTH.finditer(context):
        rest = context[found.end() :]
        year = YEAR.match(rest.lstrip())
        end = found.end() + (len(rest) - len(rest.lstrip()) + year.end() if year else 0)
        start = found.start()
        if year is None:
            # Turkish writes the year first as readily as last: "2021 Şubat'ta" beside
            # "Şubat 2021'de". Read only forwards, the year and the month became two
            # mentions with no figure between them, which is the shape `own_dated_part`
            # takes as "this clause does not pair dates with figures" — so it gave up and
            # returned the whole sentence. Live 2026-09-22: an answer naming four months
            # and their four correct real balances was withheld entire, each figure
            # refused for another month's period.
            leading = re.search(r"(?<![\w-])((?:19|20)\d{2})\s*$", context[: found.start()])
            if leading is not None and not has_amount_context(
                context, leading.start(1), leading.end(1)
            ):
                start = leading.start(1)
        spans.append((start, end))
    for found in YEAR.finditer(context):
        if has_amount_context(context, found.start(), found.end()):
            continue
        if not any(start <= found.start() < end for start, end in spans):
            spans.append((found.start(), found.end()))
    return sorted(spans)


def own_dated_part(clause: str, position: int) -> str:
    """The part of a clause a figure is dated by, when each date introduces its own figure.

    "Ocak 2021'de 281.234 milyon TL olan bakiye Aralık 2025'te 801.438 milyon TL'ye ulaştı."
    is how an analyst says it, and both figures are right; read as one context, each figure
    was refused for the other's month, and the turn paid a second writer call to have the
    sentence cut in two (live E7; one stored repair took 1,036 s). The reading is only
    narrowed where the clause itself pairs them: a figure stands between every two dated
    mentions and after the last one. "2021 ve 2022 yıllarında 100 oldu" pairs nothing, so
    both years still have to hold, and a figure written before the first date keeps the
    whole clause.
    """
    mentions = _dated_mentions(clause)
    if len(mentions) < 2 or position < mentions[0][0]:
        return clause
    bounds = [start for start, _ in mentions] + [len(clause)]
    for (_, end), following in zip(mentions, bounds[1:], strict=True):
        between = clause[end:following]
        if not any(
            not is_list_marker(clause, end + found.start(), end + found.end())
            for found in re.finditer(r"\d+", between)
        ):
            return clause
    for start, following in zip(bounds, bounds[1:], strict=False):
        if start <= position < following:
            return clause[start:following]
    return clause


def period_fault(
    clause: str,
    prefix: str,
    value: ResultValue,
    references: Sequence[date] = (),
    position: int | None = None,
) -> str | None:
    # A leading date may scope several columns. An explicit local date takes
    # precedence, so a later column cannot borrow another column's month.
    if references:
        masked = mask_price_references(clause, references)
        # Masking keeps every offset only when it keeps the length; otherwise the
        # figure's position no longer means anything and the whole clause is read.
        if len(masked) != len(clause):
            position = None
        clause = masked
        prefix = mask_price_references(prefix, references)
    if position is not None:
        clause = own_dated_part(clause, position)
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
    # A "2024-03" written on its own is a period like any other. It was matched by none
    # of the three patterns below, so a claim attributed to a month outside the result's
    # coverage passed unchecked. (Taken from PR #316.)
    year_months = list(YEAR_MONTH.finditer(context))
    months = list(MONTH.finditer(context))
    if not dates and not years and not months and not year_months:
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
    for match in year_months:
        year, month = map(int, match[0].split("-"))
        if (
            not (period.start.year, period.start.month)
            <= (year, month)
            <= (period.end.year, period.end.month)
        ):
            return fault
    for match in months:
        month = MONTHS[fold(match[1])]
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
    actual = UNITS.get(fold(value.unit or ""), fold(value.unit or ""))
    if any(unit != actual for unit in units):
        return f"Explicit unit/currency {units!r} conflicts with recorded unit {value.unit!r}"
    return None
