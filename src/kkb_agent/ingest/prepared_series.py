"""Reviewed display names for prepared official series (M6-25).

Plans are produced in one shot, so a planner cannot read catalog_search output
before choosing arguments, and the BDDK internal id is an opaque hash it could
never guess. The tools therefore describe the prepared series they can read.

Names come only from the reviewed M3-05 BDDK housing selectors and the M3-07
EVDS registry — code constants, never source text — and only for series that
are actually registered in the connected lakehouse. They name meaning and
ambiguity explicitly (stock, not disbursement; new-loan rate; base years).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kkb_agent.ingest.bddk_monthly import BddkSelector
from kkb_agent.ingest.evds_series import REVIEWED_SERIES

if TYPE_CHECKING:  # pragma: no cover
    from duckdb import DuckDBPyConnection

_BDDK_COMPONENTS = {
    "TOTAL": "toplam (TP ve YP birlikte)",
    "TP": "yalnız TP bileşeni",
    "YP": "yalnız YP bileşeni",
}
_EVDS_NAMES = {
    "TP.KTF12": (
        "EVDS konut kredisi faiz oranı: yeni kullandırılan TL konut kredileri (akım), "
        "mevduat, kalkınma ve yatırım bankaları, yüzde, haftalık (Cuma)"
    ),
    "TP.TUKFIY2025.GENEL": "TÜFE genel endeksi (2025=100), TÜİK, aylık",
    "TP.GENENDEKS.T1": "TÜFE genel endeksi (2003=100), TÜİK, aylık; çapraz kontrol serisi",
    "TP.KFE.TR": "Konut fiyat endeksi, Türkiye geneli (2023=100), TCMB, aylık",
}


def reviewed_series_names() -> dict[str, str]:
    names: dict[str, str] = {}
    for component, text in _BDDK_COMPONENTS.items():
        selector = BddkSelector(
            bulletin_family="monthly",
            table=4,
            row=2,
            bank_group=10001,
            presentation_currency="TL",
            value_dimension=component,  # type: ignore[arg-type]
        )
        names[selector.internal_id()] = (
            f"BDDK Aylık Bülten konut kredisi bakiyesi, sektör, {text}, milyon TL, "
            "ay sonu stok (kullandırım değil)"
        )
    for code, series in REVIEWED_SERIES.items():
        names[series.series_id] = _EVDS_NAMES.get(
            code,
            f"{series.datagroup_title}: {series.title}; {series.unit}, "
            f"{series.frequency.value}, {series.stock_flow.value}",
        )
    return names


def prepared_series_names(connection: DuckDBPyConnection) -> dict[str, str]:
    """Reviewed names for the series this lakehouse actually holds, in id order."""
    registered = {
        row[0] for row in connection.execute("SELECT series_id FROM silver_series").fetchall()
    }
    return {sid: name for sid, name in sorted(reviewed_series_names().items()) if sid in registered}


def prepared_series_coverage(connection: DuckDBPyConnection) -> dict[str, str]:
    """The window of non-null observations each stored series holds ("2021-01..2026-06").

    Shown beside a series' meaning in the tool descriptions the planner reads, so it
    never has to guess whether a series covers the table it is transforming (live
    R2, 2026-09-19: the planner doubted the 2025-based CPI covered 2024 and chose
    the 2003-based cross-check series instead). Never part of a display name.
    """
    rows = connection.execute(
        "SELECT series_id, min(period_end), max(period_end) FROM silver_observations "
        "WHERE value IS NOT NULL GROUP BY series_id ORDER BY series_id"
    ).fetchall()
    return {
        str(row[0]): f"{row[1]:%Y-%m}..{row[2]:%Y-%m}"
        for row in rows
        if row[1] is not None and row[2] is not None
    }
