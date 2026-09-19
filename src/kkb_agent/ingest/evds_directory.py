"""EVDS's own directory (DEC-177): datagroups pinned, series declared from the source's fields.

EVDS publishes its whole catalogue without credentials: one response lists every category
and datagroup (title, frequency, publisher and, for most, the unit), and one response per
datagroup lists its series with their names, native frequency and aggregation flags. The
reviewed registry (`evds_series`) names 26 of those series one by one; this module lets any
other listed series be *declared* without anyone typing its code:

* frequency, weekly anchor and request code from `FREQUENCY_STR`;
* unit and scale from the datagroup's own `BIRIMI`, else from a parenthesis in the series or
  datagroup title, through a closed vocabulary (`_UNITS`);
* rate / index / stock / flow from that unit and the source's own `SUMABLE` flag;
* the aggregation policy from `DEFAULT_AGG_METHOD` and the `*ABLE` flags, as published.

Whatever cannot be derived stays undeclared and the series is listed but not fetched:
nothing is guessed, and nothing comes from a model. No retrieval happens here except the
bounded, fixed-address series-list read.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from pydantic import JsonValue, SecretStr

from kkb_agent.catalog.records import AggregationPolicy
from kkb_agent.core import Aggregation, Frequency, Scale, StockFlow, WeeklyAnchor
from kkb_agent.ingest.evds_directory_listing import DIRECTORY, DIRECTORY_SHA256
from kkb_agent.ingest.evds_series import REVIEWED_SERIES, ReviewedEvdsSeries
from kkb_agent.ingest.safe_fetch import FetchLimits, FetchRequest

DIRECTORY_URL: Final = "https://evds3.tcmb.gov.tr/igmevdsms-dis/categories/withDatagroups/type=json"
SERIES_LIST_URL: Final = "https://evds3.tcmb.gov.tr/igmevdsms-dis/serieList/fe/type=json&code="
SERIES_LIST_LIMITS: Final = FetchLimits(
    max_url_chars=256,
    max_header_bytes=16 * 1024,
    max_response_bytes=4 * 1024 * 1024,
    max_decompressed_bytes=8 * 1024 * 1024,
    max_redirects=0,
)
MAX_LISTED_SERIES: Final = 5000
MAX_LISTED_GROUPS: Final = 5000
_GROUP_CODE = re.compile(r"^[A-Za-z0-9_]{2,60}$")
_SERIES_CODE = re.compile(r"^TP\.[A-Z0-9_.]{1,60}$")

#: `FREQUENCY_STR` -> calendar, the client's request code, the weekly anchor (EVDS_SERIES_METADATA).
FREQUENCIES: Final[dict[str, tuple[Frequency, int, WeeklyAnchor | None]]] = {
    "GÜNLÜK": (Frequency.DAILY, 1, None),
    "İŞ GÜNÜ": (Frequency.BUSINESS_DAY, 2, None),
    "HAFTALIK(CUMA)": (Frequency.WEEKLY, 3, WeeklyAnchor.FRIDAY),
    "HAFTALIK(ÇARŞAMBA)": (Frequency.WEEKLY, 3, WeeklyAnchor.WEDNESDAY),
    "AYLIK": (Frequency.MONTHLY, 5, None),
    "ÜÇ AYLIK": (Frequency.QUARTERLY, 6, None),
    "YILLIK": (Frequency.ANNUAL, 8, None),
}
_AGGREGATIONS: Final = {
    "avg": Aggregation.AVERAGE,
    "sum": Aggregation.SUM,
    "last": Aggregation.LAST,
    "first": Aggregation.FIRST,
    "min": Aggregation.MIN,
    "max": Aggregation.MAX,
}
_SCALES: Final = {
    "": Scale.ONE,
    "bin": Scale.THOUSAND,
    "milyon": Scale.MILLION,
    "milyar": Scale.BILLION,
}
_CURRENCIES: Final = {
    "tl": "TRY",
    "türk lirası": "TRY",
    "abd doları": "USD",
    "abd dolari": "USD",
    "euro": "EUR",
}
_PERCENT: Final = frozenset({"yüzde", "%", "oran", "net yüzde değişim"})
_COUNTS: Final = frozenset({"adet", "kişi", "kez", "işlem"})
#: What a price is quoted per: "TL/Gr", "ABD Doları/Ons", "TL/kg", "TL/Adet".
_QUANTITIES: Final = {
    "gr": "g",
    "gram": "g",
    "kg": "kg",
    "ons": "oz",
    "ton": "t",
    "adet": "piece",
}
_PRICE_CURRENCIES: Final = {**_CURRENCIES, "usd": "USD", "eur": "EUR", "try": "TRY"}
_BASE = re.compile(r"(?<![0-9])((?:19|20)[0-9]{2})\s*=\s*100(?![0-9])")
_CUMULATIVE = re.compile(r"k[üu]m[üu]latif|birikimli", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ListedGroup:
    """One datagroup as EVDS lists it: what a person browsing "Tüm Seriler" sees."""

    code: str
    title: str
    title_eng: str
    category: str
    frequency_str: str
    data_source: str
    unit_text: str
    archived: bool


def listed_groups() -> tuple[ListedGroup, ...]:
    return tuple(ListedGroup(**item) for item in DIRECTORY["groups"])


def _words(value: object) -> str:
    return " ".join(str(value or "").split())


def directory_request() -> FetchRequest:
    """The one fixed-address GET that lists every category and datagroup EVDS publishes."""
    return FetchRequest(
        source_ref="evds:directory",
        url=SecretStr(DIRECTORY_URL),
        accepted_media_types=("application/json",),
    )


def parse_directory(payload: bytes) -> tuple[ListedGroup, ...]:
    """Every datagroup of EVDS's own directory, by code; what the harvest pins and a refresh
    compares. Only what a person browsing "Tüm Seriler" reads is kept: no series, no value."""
    if not isinstance(payload, bytes) or len(payload) > SERIES_LIST_LIMITS.max_decompressed_bytes:
        raise ValueError("directory exceeds its budget")
    categories = json.loads(payload.decode("utf-8"))
    if not isinstance(categories, list) or not all(isinstance(item, dict) for item in categories):
        raise ValueError("directory is not an array of categories")
    titles = {item.get("CATEGORY_ID"): _words(item.get("TOPIC_TITLE_TR")) for item in categories}
    parents = {item.get("CATEGORY_ID"): item.get("UST_CATEGORY_ID") for item in categories}

    def path(category: object) -> str:
        parts: list[str] = []
        seen: set[object] = set()
        current = category
        while current in titles and current not in seen:
            seen.add(current)
            parts.append(titles[current])
            current = parents.get(current)
        return " > ".join(reversed(parts))

    groups: dict[str, ListedGroup] = {}
    for category in categories:
        for group in category.get("DATAGROUPS") or []:
            code = _words(group.get("DATAGROUP_CODE")) if isinstance(group, dict) else ""
            if not _GROUP_CODE.fullmatch(code):
                continue
            title = _words(group.get("DATAGROUP_TYPE"))
            groups.setdefault(
                code,
                ListedGroup(
                    code=code,
                    title=title,
                    title_eng=_words(group.get("DATAGROUP_TYPE_ENG")),
                    category=path(category.get("CATEGORY_ID")),
                    frequency_str=_words(group.get("FREQUENCY_STR")),
                    data_source=_words(group.get("DATASOURCE")),
                    unit_text=_words(group.get("BIRIMI")),
                    archived="arşiv" in title.lower(),
                ),
            )
    if len(groups) > MAX_LISTED_GROUPS:
        raise ValueError("directory lists more datagroups than its budget")
    return tuple(groups[code] for code in sorted(groups))


def _fold(text: str) -> str:
    return " ".join(text.replace("İ", "i").replace("I", "ı").lower().split())


@dataclass(frozen=True, slots=True)
class _Unit:
    unit: str
    scale: Scale
    base_year: int | None = None


def _unit_of(text: str) -> _Unit | None:
    """A unit from one source text through the closed vocabulary, or None."""
    folded = _fold(text)
    if not folded:
        return None
    base = _BASE.search(folded)
    if base is not None or folded in ("endeks", "miktar endeks"):
        return _Unit("index", Scale.ONE, int(base.group(1)) if base else None)
    if folded in _PERCENT:
        return _Unit("percent", Scale.ONE)
    money, slash, per = folded.partition("/")
    if slash and money.strip() in _PRICE_CURRENCIES and per.strip() in _QUANTITIES:
        # A price per quantity is its own unit; it is never added up or compared with money.
        return _Unit(f"{_PRICE_CURRENCIES[money.strip()]}/{_QUANTITIES[per.strip()]}", Scale.ONE)
    scale_word, _, rest = folded.partition(" ")
    if scale_word in _SCALES and rest:
        if rest in _CURRENCIES:
            return _Unit(_CURRENCIES[rest], _SCALES[scale_word])
        if rest in _COUNTS:
            return _Unit("count", _SCALES[scale_word])
    if folded in _CURRENCIES:
        return _Unit(_CURRENCIES[folded], Scale.ONE)
    if folded in _COUNTS:
        return _Unit("count", Scale.ONE)
    return None


def _parenthesised(title: str) -> list[str]:
    return [part.strip() for part in re.findall(r"\(([^()]{1,40})\)", title)]


def _declared_unit(group: ListedGroup, name: str) -> _Unit | None:
    """The datagroup's own unit field first; then a parenthesis of the series or group title.

    A parenthesis may hold several comma-separated qualifiers ("TL, Akım, %"): the last one
    that is a unit wins, which is how EVDS writes them. A percent sign in the series name
    overrides a datagroup unit that only names the statistic ("Ağırlıklı ortalama").
    """
    own = [piece.strip() for text in _parenthesised(name) for piece in text.split(",")]
    # EVDS also writes a unit after a dash: "Altın - Kapanış Fiyatı - TL/kg".
    own.append(name.rpartition(" - ")[2].strip() if " - " in name else "")
    stated = [unit for unit in map(_unit_of, own) if unit is not None]
    # What the series says about itself is more specific than its datagroup's one field: a
    # "(%)" row of a datagroup counted in "Bin kişi" is a rate (live: "İşsizlik oranı (%)"),
    # and a price names its own quotation. A bare currency in a name is not taken from it:
    # "(USD) ABD Doları (Döviz Alış)" is the thing priced, in the datagroup's Turkish lira.
    specific = next((u for u in stated if u.unit == "percent" or "/" in u.unit), None)
    if specific is not None:
        return specific
    candidates = [group.unit_text, *own]
    for text in _parenthesised(group.title):
        candidates.extend(piece.strip() for piece in text.split(","))
    found = [unit for unit in map(_unit_of, candidates) if unit is not None]
    if not found:
        return None
    first = found[0]
    if first.unit == "index" and first.base_year is None:
        based = next((u for u in found if u.unit == "index" and u.base_year is not None), None)
        return based  # an index without a stated base year is not declared
    percent = next((u for u in found if u.unit == "percent"), None)
    return percent if percent is not None and _unit_of(group.unit_text) is None else first


def _flag(raw: Mapping[str, JsonValue], key: str) -> bool | None:
    value = raw.get(key)
    return bool(value) if value in (0, 1) else None


def declare_series(group: ListedGroup, raw: Mapping[str, JsonValue]) -> ReviewedEvdsSeries | None:
    """One listed series with everything the loader and the catalogue need, or None.

    None means "listed, not fetched": an unsupported calendar, no derivable unit, an index
    without a base year, a cumulative wording nobody measured, or a malformed entry.
    """
    code, name = raw.get("SERIE_CODE"), raw.get("SERIE_NAME")
    if not isinstance(code, str) or not _SERIES_CODE.fullmatch(code):
        return None
    if not isinstance(name, str) or not name.strip() or len(name) > 400:
        return None
    if code in REVIEWED_SERIES:
        return REVIEWED_SERIES[code]
    calendar = FREQUENCIES.get(str(raw.get("FREQUENCY_STR") or group.frequency_str))
    unit = _declared_unit(group, name)
    aggregation = _AGGREGATIONS.get(str(raw.get("DEFAULT_AGG_METHOD")))
    if calendar is None or unit is None or aggregation is None:
        return None
    if _CUMULATIVE.search(name) or _CUMULATIVE.search(group.title):
        return None
    frequency, request_frequency, anchor = calendar
    summable = _flag(raw, "SUMABLE")
    if unit.unit == "percent":
        kind = StockFlow.RATE
    elif unit.unit == "index":
        kind = StockFlow.INDEX
    elif "/" in unit.unit:
        kind = StockFlow.STOCK  # a quoted price is a level, whatever the summable flag says
    elif summable is None:
        return None
    else:
        kind = StockFlow.FLOW if summable else StockFlow.STOCK
    if kind in (StockFlow.RATE, StockFlow.INDEX) and aggregation is Aggregation.SUM:
        return None  # the source's own flags contradict the unit; leave it undeclared
    flags = {
        "sum": summable,
        "average": _flag(raw, "AVGABLE"),
        "first": _flag(raw, "FIRSTABLE"),
        "last": _flag(raw, "LASTABLE"),
        "min": _flag(raw, "MINABLE"),
        "max": _flag(raw, "MAXABLE"),
    }
    if flags.get(aggregation.value) is False:
        # The source forbids its own display default (live 2026-09-19: every flag is 0 for the
        # seasonally adjusted labour series). The series is still read at its own frequency;
        # it declares no way to be reduced, so a reduction is refused rather than guessed.
        aggregation = Aggregation.UNKNOWN
    policy = AggregationPolicy(default=aggregation, **flags)
    english = raw.get("SERIE_NAME_ENG")
    return ReviewedEvdsSeries(
        code=code,
        title=" ".join(name.split()),
        title_eng=" ".join(english.split()) if isinstance(english, str) else "",
        datagroup=group.code,
        datagroup_title=group.title,
        data_source=group.data_source,
        evidence_sha256=DIRECTORY_SHA256,
        frequency=frequency,
        request_frequency=request_frequency,
        unit=unit.unit,
        stock_flow=kind,
        anchor=anchor,
        base_year=unit.base_year,
        note=(
            f"EVDS veri grubu: {group.title} ({group.category}). Birim: "
            f"{group.unit_text or 'seri adından'}; sıklık: {group.frequency_str}. Kaynağın kendi "
            "dizininden: birim, sıklık ve toplama kuralı kaynağın alanlarından; tek tek "
            "incelenmedi."
        ),
        scale=unit.scale,
        aggregation=aggregation,
        policy=policy,
    )


def series_list_request(group_code: str, *, listed: frozenset[str] = frozenset()) -> FetchRequest:
    """The one fixed-address GET that lists a datagroup's series; the code is a listed one.

    `listed` names datagroups a refresh found in EVDS's live directory after the pin.
    """
    if not _GROUP_CODE.fullmatch(group_code) or (
        group_code not in listed
        and group_code not in {item["code"] for item in DIRECTORY["groups"]}
    ):
        raise ValueError("datagroup is not in the EVDS directory")
    return FetchRequest(
        source_ref="evds:serie-list:" + group_code,
        url=SecretStr(SERIES_LIST_URL + group_code),
        accepted_media_types=("application/json",),
    )


def parse_series_list(payload: bytes) -> tuple[tuple[dict[str, JsonValue], ...], str]:
    """The listed series as the source wrote them, and the digest of exactly those bytes."""
    if not isinstance(payload, bytes) or len(payload) > SERIES_LIST_LIMITS.max_decompressed_bytes:
        raise ValueError("series list exceeds its budget")
    document = json.loads(payload.decode("utf-8"))
    if not isinstance(document, list) or len(document) > MAX_LISTED_SERIES:
        raise ValueError("series list is not a bounded array")
    rows = tuple(item for item in document if isinstance(item, dict))
    if len(rows) != len(document):
        raise ValueError("series list entry is not an object")
    return rows, hashlib.sha256(payload).hexdigest()
