"""A month the bulletin publishes after a series was stored reaches the next question.

Live 2026-09-23 (A3): asked to August, the answer was read from a series ending in June,
although the bulletin had published July (Tüketici Kredileri - Taşıt, 42,107 million
TL). Three things held it back: the window ended three months before the clock, a
stored series was never fetched again, and a "not yet" reply would have been kept as
the month's answer. All retrieval here is injected; no network, no official values.
"""

from __future__ import annotations

import json
from datetime import date

import pytest
from test_bddk_monthly_load import selector

from kkb_agent.ingest import bddk_monthly_load as load
from kkb_agent.ingest.acquisition import (
    AcquiringInspector,
    AcquisitionStore,
    OfficialSources,
    TurnAcquirer,
    bddk_window,
)
from kkb_agent.ingest.bddk_monthly import MonthlyPeriod
from kkb_agent.ingest.bddk_monthly_request import MonthlyRange, MonthlyRequest, unpublished
from kkb_agent.ingest.safe_fetch import FetchSuccess
from kkb_agent.lakehouse import open_lakehouse
from kkb_agent.lakehouse.store import LakehouseError


def months(start, end):
    return MonthlyRange(
        start=MonthlyPeriod(year=start[0], month=start[1]),
        end=MonthlyPeriod(year=end[0], month=end[1]),
    )


def reply(req, total):
    return {
        "success": True,
        "Json": {
            "caption": (
                f"Tüketici Kredileri (milyon TL), Dönem:{req.period.year}/{req.period.month}"
            ),
            "colNames": ["", "", "", "BasitFont", "TP", "YP", "Toplam"],
            "data": {
                "page": "1",
                "total": "1",
                "records": "1",
                "rows": [
                    {
                        "id": "2",
                        "cell": ["Sektör", 2, "Tüketici Kredileri - Konut", "", total, 0, total],
                    }
                ],
            },
        },
    }


NOT_YET = {"success": False, "error": "2026 yılının en son 7 ayına ait veri bulunmaktadır!"}


class Bulletin:
    """Publishes `values[(year, month)]`; any other month is answered "not yet"."""

    def __init__(self, values):
        self.values = dict(values)
        self.asked = []

    def __call__(self, req):
        self.asked.append((req.period.year, req.period.month))
        key = (req.period.year, req.period.month)
        body = reply(req, self.values[key]) if key in self.values else NOT_YET
        return FetchSuccess(
            source_ref=req.fetch_request().source_ref,
            content=json.dumps(body, ensure_ascii=False).encode(),
            media_type="application/json",
            http_status=200,
        )


@pytest.fixture
def lake(tmp_path):
    with open_lakehouse(tmp_path / "lake") as result:
        yield result


def stored(lake):
    return lake.connection.execute(
        "SELECT period_end, value FROM silver_observations ORDER BY period_end"
    ).fetchall()


def test_the_window_asks_up_to_last_month():
    assert bddk_window(date(2026, 9, 23)).end == MonthlyPeriod(year=2026, month=8)


def test_newest_months_not_yet_published_are_left_out(lake):
    bulletin = Bulletin({(2026, 1): 10, (2026, 2): 11, (2026, 3): 12})
    done = load.ingest_monthly(lake, selector(), months((2026, 1), (2026, 5)), retrieve=bulletin)
    assert done.months == 3
    assert [value for _, value in stored(lake)] == [10, 11, 12]
    # The same published months fetched on another day are the same batch.
    again = load.ingest_monthly(lake, selector(), months((2026, 1), (2026, 4)), retrieve=bulletin)
    assert again.already_present and again.manifest_id == done.manifest_id


@pytest.mark.parametrize(
    "published",
    [
        # Three "not yet" at the end is not a publication lag.
        {(2026, 1): 10, (2026, 2): 11},
        # A published month after one said to be missing is not a lag either.
        {(2026, 1): 10, (2026, 3): 12, (2026, 4): 13, (2026, 5): 14},
    ],
)
def test_anything_else_unpublished_is_refused(lake, published):
    with pytest.raises(load.MonthlyLoadError) as refused:
        load.ingest_monthly(
            lake, selector(), months((2026, 1), (2026, 5)), retrieve=Bulletin(published)
        )
    assert refused.value.code is load.MonthlyLoadCode.RESPONSE_INVALID
    assert stored(lake) == []


def test_a_stored_series_is_extended_by_newly_published_months(lake):
    bulletin = Bulletin({(2026, 2): 11, (2026, 3): 12})
    load.ingest_monthly(lake, selector(), months((2026, 2), (2026, 3)), retrieve=bulletin)
    # Later: one month published after it, and the window starts a month earlier.
    bulletin.values.update({(2026, 1): 10, (2026, 4): 13})
    grown = load.ingest_monthly(lake, selector(), months((2026, 1), (2026, 5)), retrieve=bulletin)
    assert not grown.already_present
    assert [value for _, value in stored(lake)] == [10, 11, 12, 13]


def test_a_revised_month_is_a_conflict_and_the_store_is_unchanged(lake):
    bulletin = Bulletin({(2026, 1): 10, (2026, 2): 11})
    load.ingest_monthly(lake, selector(), months((2026, 1), (2026, 2)), retrieve=bulletin)
    before = stored(lake)
    bulletin.values.update({(2026, 2): 99, (2026, 3): 12})
    with pytest.raises(load.MonthlyLoadError) as refused:
        load.ingest_monthly(lake, selector(), months((2026, 1), (2026, 3)), retrieve=bulletin)
    assert refused.value.code is load.MonthlyLoadCode.VERSION_CONFLICT
    assert stored(lake) == before


def test_a_not_yet_reply_is_never_kept_as_the_months_answer(tmp_path):
    store = AcquisitionStore(tmp_path / "kept")
    bulletin = Bulletin({(2026, 1): 10})
    calls: list[bool] = []
    cached = store.cached(bulletin, calls)
    for month in (1, 2, 1, 2):
        cached(MonthlyRequest(selector=selector(), period=MonthlyPeriod(year=2026, month=month)))
    # January is kept after its first read; February is asked again every time.
    assert calls == [True, True, False, True]
    assert unpublished(json.dumps(NOT_YET).encode())
    assert not unpublished(b'{"success": true}') and not unpublished(b"not json")


def test_a_move_that_fails_leaves_the_series_as_it_was(lake):
    bulletin = Bulletin({(2026, 1): 10, (2026, 2): 11})
    done = load.ingest_monthly(lake, selector(), months((2026, 1), (2026, 2)), retrieve=bulletin)
    before = stored(lake)
    series_id = selector().internal_id()
    rows, _ = lake.extension_of(series_id, [])
    with pytest.raises(LakehouseError):
        # Two rows for one month: the second step refuses, the first is undone.
        lake.move_series(series_id, artifact_id=done.manifest_id, before=rows, after=rows + rows)
    assert stored(lake) == before


class Published:
    """Every month from 2020-12 through `through` is published; later ones are "not yet"."""

    def __init__(self, through):
        self.through = through
        self.asked = 0

    def __call__(self, req):
        self.asked += 1
        key = (req.period.year, req.period.month)
        body = reply(req, 1000 + req.period.month) if key <= self.through else NOT_YET
        return FetchSuccess(
            source_ref=req.fetch_request().source_ref,
            content=json.dumps(body, ensure_ascii=False).encode(),
            media_type="application/json",
            http_status=200,
        )


def test_a_read_past_the_stored_end_brings_the_newly_published_month(lake):
    today = date(2026, 9, 23)
    earlier = Published(through=(2026, 6))
    first = TurnAcquirer(lake, date(2026, 8, 1), sources=OfficialSources(bddk=earlier))
    assert first.acquire(selector().internal_id()).stored
    series_id = selector().internal_id()
    assert max(end for end, _ in stored(lake)) == date(2026, 6, 30)

    later = Published(through=(2026, 7))
    inspector = AcquiringInspector(
        None, TurnAcquirer(lake, today, sources=OfficialSources(bddk=later))
    )  # type: ignore[arg-type]
    inspector.refresh(lake.connection, series_id, date(2026, 6, 30))
    assert later.asked == 0  # nothing asked past what is stored
    inspector.refresh(lake.connection, series_id, date(2026, 8, 31))
    assert max(end for end, _ in stored(lake)) == date(2026, 7, 31)
    assert stored(lake)[-1][1] == 1007
