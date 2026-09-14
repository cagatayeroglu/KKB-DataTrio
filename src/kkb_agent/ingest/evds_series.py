"""M3-07 bounded reviewed EVDS series metadata; no retrieval or storage.

Each entry was resolved from live EVDS3 catalog metadata on 2026-09-14 (series
list per datagroup plus the category tree) and is pinned to that response's
SHA-256. Only these explicit official series codes may reach the M3-08 request
path. A code that merely looks valid, a datagroup code or a similar display name
is refused: `TP.KTF12` and `TP.KBK.TRY.18` differ only by a comma in their names
but are deposit-bank interest rates versus participation-bank profit shares.

Declarations come from source fields, except where noted on the entry. EVDS
`STATUS: 1` is recorded as evidence but its meaning is undocumented, so catalog
status stays UNKNOWN. Coverage is established by ingestion, not declared here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Final

from kkb_agent.catalog.records import AggregationPolicy, CatalogRecord, SourceGroup
from kkb_agent.core import (
    Aggregation,
    CumulativeKind,
    Frequency,
    Scale,
    SourceRef,
    StockFlow,
    WeeklyAnchor,
)
from kkb_agent.lakehouse.semantics import SeriesSemantics

PROVIDER: Final = "EVDS"
REVIEWED_AT: Final = datetime(2026, 9, 14, tzinfo=UTC)
SERIES_LIST_LOCATOR: Final = "https://evds3.tcmb.gov.tr/igmevdsms-dis/serieList/fe/type=json&code="
# Every reviewed series publishes the same flags: avg default; sum explicitly forbidden.
_AVERAGE_NOT_SUM = AggregationPolicy(
    default=Aggregation.AVERAGE,
    sum=False,
    average=True,
    first=True,
    last=True,
    min=True,
    max=True,
)


class UnreviewedSeries(ValueError):
    """The code is not in the reviewed EVDS registry; nothing is inferred for it."""


@dataclass(frozen=True, slots=True)
class ReviewedEvdsSeries:
    code: str
    title: str
    title_eng: str
    datagroup: str
    datagroup_title: str
    data_source: str
    evidence_sha256: str
    frequency: Frequency
    #: EVDS client request code: 3 weekly, 5 monthly. Always the native cadence.
    request_frequency: int
    unit: str
    stock_flow: StockFlow
    anchor: WeeklyAnchor | None = None
    base_year: int | None = None
    note: str = ""

    @property
    def series_id(self) -> str:
        return f"{PROVIDER}:{self.code}"

    @property
    def response_key(self) -> str:
        """EVDS returns observation columns with dots replaced by underscores."""
        return self.code.replace(".", "_")


_SERIES = (
    ReviewedEvdsSeries(
        code="TP.KTF12",
        title="Konut Kredisi (TL, Akım, %)",
        title_eng="Housing Loans (TRY) (Flow, %)",
        datagroup="bie_kt100h",
        datagroup_title="Kredi Faiz Oranları (Akım)",
        data_source="Mevduat, Kalkınma ve Yatırım Bankaları",
        evidence_sha256="b05143c4693d5b9e6057b5caaeb07123baefcbf594d1f57d9847481bbcde14c9",
        frequency=Frequency.WEEKLY,
        request_frequency=3,
        unit="percent",
        stock_flow=StockFlow.RATE,
        anchor=WeeklyAnchor.FRIDAY,
        note=(
            "Weighted-average interest rate on new TRY housing loans (flow) by deposit, "
            "development and investment banks; not participation-bank profit shares "
            "(TP.KBK.TRY.18) and not the outstanding-portfolio rate (TP.BKR.TRY.18)."
        ),
    ),
    ReviewedEvdsSeries(
        code="TP.TUKFIY2025.GENEL",
        title="Genel Endeks",
        title_eng="General Index",
        datagroup="bie_tukfiy2025",
        datagroup_title="Tüketici Fiyat Endeksi (2025=100)",
        data_source="TÜİK",
        evidence_sha256="e9e556bed380546ce930ae192171f71f5e37e3a6e0367b370e66c2bb60d62f67",
        frequency=Frequency.MONTHLY,
        request_frequency=5,
        unit="index",
        stock_flow=StockFlow.INDEX,
        base_year=2025,
        note="Headline CPI, 2025=100 per the datagroup title; earlier periods are linked.",
    ),
    ReviewedEvdsSeries(
        code="TP.GENENDEKS.T1",
        title="Genel Endeks (2003=100)",
        title_eng="General Endeks (2003=100)",
        datagroup="bie_tukfiy2003",
        datagroup_title="Tüketici Fiyat Endeksi (Genel) (2003=100)",
        data_source="TÜİK",
        evidence_sha256="bcb8071d41ebefbe5d4b59b87ea8522eb64326e539024570a9c0f5986f53182a",
        frequency=Frequency.MONTHLY,
        request_frequency=5,
        unit="index",
        stock_flow=StockFlow.INDEX,
        base_year=2003,
        note="Headline CPI on the 2003=100 base; kept as an independent cross-check.",
    ),
    ReviewedEvdsSeries(
        code="TP.KFE.TR",
        title="Konut Fiyat Endeksi (KFE)",
        title_eng="Residential Property Price Index (RPPI)",
        datagroup="bie_kfe",
        datagroup_title="Konut Fiyat Endeksi",
        data_source="TCMB",
        evidence_sha256="fef75407bf6a999779594efc1d2d500227310605aadb1f3fee7edaf52a079c1b",
        frequency=Frequency.MONTHLY,
        request_frequency=5,
        unit="index",
        stock_flow=StockFlow.INDEX,
        base_year=2023,
        note=(
            "National KFE. EVDS titles carry no base label; 2023=100 is reviewed from the "
            "published observations (2023 mean 99.999 on 2026-09-14), not from a title."
        ),
    ),
)

# M3-08 coverage expansion: explicit selections reviewed against the same pinned
# source lists. No runtime source title, alias or arbitrary code adds authority.

_ADDITIONAL_RATE_METADATA = (
    ("TP.KTF10", "İhtiyaç Kredisi (TL, Akım, %)", "Personal Loans (TRY) (Flow, %)"),
    (
        "TP.KTF101",
        "İhtiyaç Kredisi (KMH Dahil) (TL, Akım, %)",
        "Personal Loans (TRY) (Including Real Person Overdraft Account) (Flow, %)",
    ),
    ("TP.KTF11", "Taşıt Kredisi (TL, Akım, %)", "Vehicle Loans (TRY) (Flow, %)"),
    ("TP.KTF17", "Ticari Krediler (TL, Akım, %)", "Commercial Loans (TRY) (Flow, %)"),
    ("TP.KTF17.EUR", "Ticari Krediler (Euro, Akım, %)", "Commercial Loans (EUR) (Flow, %)"),
    ("TP.KTF17.USD", "Ticari Krediler (ABD doları, Akım,%)", "Commercial Loans (USD) (Flow, %)"),
    (
        "TP.KTF18",
        "Ticari Krediler (Tüzel Kişi KMH ve Kurumsal Kredi Kartları Hariç) (TL, Akım, %)",
        "Commercial Loans (TRY) (Excluding Corporate Overdraft Account and Corporate Credit "
        "Cards) (Flow, %)",
    ),
    (
        "TP.KTFTUK",
        "Tüketici Kredisi (İhtiyaç+Taşıt+Konut) (TL, Akım, %)",
        "Consumer Loans (TRY) (Personal+Vehicle+Housing) (Flow, %)",
    ),
    (
        "TP.KTFTUK01",
        "Tüketici Kredisi (KMH Dahil) (İhtiyaç+Taşıt+Konut) (TL, Akım, %)",
        "Consumer Loans (TRY) (Personal+Vehicle+Housing) (Including Real Person Overdraft "
        "Account) (Flow, %)",
    ),
)

_CPI_DIVISION_METADATA = (
    ("TP.TUKFIY2025.01", "01. Gıda Ve Alkolsüz İçecekler", "01. Food and Non-Alcoholic Beverages"),
    (
        "TP.TUKFIY2025.02",
        "02. Alkollü İçecekler, Tütün Ve Tütün Ürünleri",
        "02. Alcoholic Beverages, Tobacco and Tobacco Products",
    ),
    ("TP.TUKFIY2025.03", "03. Giyim Ve Ayakkabı", "03. Clothing and Footwear"),
    (
        "TP.TUKFIY2025.04",
        "04. Konut, Su, Elektrik, Gaz Ve Diğer Yakıtlar",
        "04. Housing, Water, Electricity, Gas, and Other Fuels",
    ),
    (
        "TP.TUKFIY2025.05",
        "05. Mobilya, Mefruşat Ve Evde Kullanılan Ekipmanlar İle Rutin Ev Bakım Ve Onarımı",
        "05. Furniture, Furnishings, and Household Equipment, and Routine Home Maintenance "
        "and Repair",
    ),
    ("TP.TUKFIY2025.06", "06. Sağlık", "06. Health"),
    ("TP.TUKFIY2025.07", "07. Ulaştırma", "07. Transportation"),
    ("TP.TUKFIY2025.08", "08. Bilgi Ve İletişim", "08. Information and Communication"),
    (
        "TP.TUKFIY2025.09",
        "09. Eğlence, Dinlence, Spor Ve Kültür",
        "09. Entertainment, Recreation, Sports, and Culture",
    ),
    ("TP.TUKFIY2025.10", "10. Eğitim Hizmetleri", "10. Educational Services"),
    (
        "TP.TUKFIY2025.11",
        "11. Lokantalar Ve Konaklama Hizmetleri",
        "11. Restaurants and Accommodation Services",
    ),
    (
        "TP.TUKFIY2025.12",
        "12. Sigorta Ve Finansal Hizmetler",
        "12. Insurance and Financial Services",
    ),
    (
        "TP.TUKFIY2025.13",
        "13. Kişisel Bakım, Sosyal Koruma Ve Çeşitli Mal Ve Hizmetler",
        "13. Personal Care, Social Protection, and Miscellaneous Goods and Services",
    ),
)

_ADDITIONAL_SERIES = (
    *(
        ReviewedEvdsSeries(
            code=code,
            title=title,
            title_eng=english,
            datagroup="bie_kt100h",
            datagroup_title="Kredi Faiz Oranları (Akım)",
            data_source="Mevduat, Kalkınma ve Yatırım Bankaları",
            evidence_sha256="b05143c4693d5b9e6057b5caaeb07123baefcbf594d1f57d9847481bbcde14c9",
            frequency=Frequency.WEEKLY,
            request_frequency=3,
            unit="percent",
            stock_flow=StockFlow.RATE,
            anchor=WeeklyAnchor.FRIDAY,
            note=(
                "New-loan interest rate, not a loan amount or outstanding-portfolio rate. "
                "Preserve the named credit category, denomination and KMH/card scope. "
                "EUR/USD identifies loan denomination; the measured value is a percent, "
                "not an exchange rate. Source allows average and forbids sum."
            ),
        )
        for code, title, english in _ADDITIONAL_RATE_METADATA
    ),
    *(
        ReviewedEvdsSeries(
            code=code,
            title=title,
            title_eng=english,
            datagroup="bie_tukfiy2025",
            datagroup_title="Tüketici Fiyat Endeksi (2025=100)",
            data_source="TÜİK",
            evidence_sha256="e9e556bed380546ce930ae192171f71f5e37e3a6e0367b370e66c2bb60d62f67",
            frequency=Frequency.MONTHLY,
            request_frequency=5,
            unit="index",
            stock_flow=StockFlow.INDEX,
            base_year=2025,
            note=(
                "CPI expenditure-division index level, 2025=100 per source group. "
                "Not headline CPI, an inflation rate or a contribution/weight. "
                "The housing/utilities division is not the residential property price "
                "index (KFE). Do not substitute it as a general deflator without an "
                "explicit matching analytical scope; missing periods remain explicit."
            ),
        )
        for code, title, english in _CPI_DIVISION_METADATA
    ),
)

REVIEWED_SERIES = MappingProxyType(
    {series.code: series for series in (*_SERIES, *_ADDITIONAL_SERIES)}
)


def reviewed_series(code: str) -> ReviewedEvdsSeries:
    try:
        return REVIEWED_SERIES[code]
    except (KeyError, TypeError):
        raise UnreviewedSeries("EVDS series is outside the reviewed registry") from None


def series_semantics(series: ReviewedEvdsSeries) -> SeriesSemantics:
    semantics = SeriesSemantics(
        unit=series.unit,
        scale=Scale.ONE,
        frequency=series.frequency,
        observation=series.stock_flow,
        cumulative=CumulativeKind.NONE,
        aggregation=Aggregation.AVERAGE,
        anchor=series.anchor,
        base_year=series.base_year,
    )
    semantics.require_resolved()
    return semantics


def catalog_record(series: ReviewedEvdsSeries) -> CatalogRecord:
    """Candidate declarations for catalog consumers; not a selection or calculation grant."""
    return CatalogRecord(
        series_id=series.series_id,
        provider=PROVIDER,
        source_series_id=series.code,
        title=series.title,
        source=SourceRef(
            source_id=f"evds:serie-list:{series.datagroup}",
            source_type="http-json",
            locator=SERIES_LIST_LOCATOR + series.datagroup,
            retrieved_at=REVIEWED_AT,
            content_hash=series.evidence_sha256,
        ),
        description=series.note,
        labels=(series.title_eng, series.data_source),
        group=SourceGroup(
            group_id=series.datagroup,
            group_title=series.datagroup_title,
            publisher=series.data_source,
        ),
        unit=series.unit,
        scale=Scale.ONE,
        frequency=series.frequency,
        weekly_anchor=series.anchor,
        stock_flow=series.stock_flow,
        cumulative=CumulativeKind.NONE,
        aggregation=_AVERAGE_NOT_SUM,
        base_year=series.base_year,
    )
