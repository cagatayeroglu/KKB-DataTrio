"""M3-08 EVDS `fe` parsing, immutable batches and publication failures.

Synthetic source-shaped responses only: the envelope, labels, variable UNIXTIME
offsets and the trailing out-of-window week mirror what EVDS returned on
2026-09-14, but no official values are used. No network or data directories.
"""

import json
from datetime import date, datetime, timedelta, timezone

import pytest

from kkb_agent.agent import AnswerStatus, ExecutionContext, gate_answer
from kkb_agent.core import Aggregation, Frequency, StockFlow, WeeklyAnchor
from kkb_agent.ingest import evds_load as load
from kkb_agent.ingest.evds_request import EvdsRequest, EvdsWindow
from kkb_agent.ingest.evds_series import reviewed_series
from kkb_agent.ingest.safe_fetch import FetchCode, FetchFailure, FetchSuccess
from kkb_agent.lakehouse import open_lakehouse
from kkb_agent.tools import LakehouseArguments, make_lakehouse_tool
from kkb_agent.tools.change_detection import read_series

MONTHLY = "TP.KFE.TR"
WEEKLY = "TP.KTF12"


def window(start=date(2021, 1, 1), end=date(2021, 6, 30)):
    return EvdsWindow(start=start, end=end)


def request(code=MONTHLY, **kwargs):
    return EvdsRequest(code=code, window=window(**kwargs))


def row(code, day, value, *, offset_hours=3):
    series = reviewed_series(code)
    local = datetime(day.year, day.month, day.day, tzinfo=timezone(timedelta(hours=offset_hours)))
    item = {
        "Tarih": day.strftime("%Y-%m" if series.frequency is Frequency.MONTHLY else "%d-%m-%Y"),
        "UNIXTIME": {"$numberLong": str(int(local.timestamp()))},
        series.response_key: value,
    }
    if series.frequency is Frequency.WEEKLY:
        item["YEARWEEK"] = f"{day.year}-{(day.timetuple().tm_yday - 1) // 7 + 1}"
    return item


def rows(req, *, trailing_week=True):
    series = req.series
    days = [
        end.replace(day=1) if series.frequency is Frequency.MONTHLY else end
        for end in load.expected_period_ends(series, req.window)
    ]
    if trailing_week and series.frequency is Frequency.WEEKLY:
        days.append(days[-1] + timedelta(days=7))  # EVDS includes the week spanning the end.
    # Early periods carry the UTC+1 midnight EVDS returned for 2021-01..03.
    return [
        row(req.code, day, f"{100 + i}.25", offset_hours=1 if day < date(2021, 4, 1) else 3)
        for i, day in enumerate(days)
    ]


def envelope(items):
    return {
        "totalCount": len(items),
        "items": items,
        "transposedItems": [],
        "transposedColumns": [],
        "seriesNames": {},
        "frequencyConversion": {},
    }


def encoded(data):
    return json.dumps(data, ensure_ascii=False).encode()


class FakeSource:
    def __init__(self, *, mutate=None, failure=None, error=None):
        self.mutate, self.failure, self.error = mutate, failure, error
        self.requests = []

    def __call__(self, req):
        self.requests.append(req)
        if self.error:
            raise self.error
        if self.failure:
            return FetchFailure(source_ref=req.fetch_request().source_ref, code=self.failure)
        data = envelope(rows(req))
        if self.mutate:
            self.mutate(data)
        return FetchSuccess(
            source_ref=req.fetch_request().source_ref,
            content=encoded(data),
            media_type="application/json",
            http_status=200,
        )


@pytest.fixture
def lake(tmp_path):
    with open_lakehouse(tmp_path / "lake") as result:
        yield result


def counts(lake):
    return tuple(
        lake.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]  # nosec B608
        for table in ("silver_series", "silver_observations", "lineage_nodes")
    )


def test_monthly_rows_parse_across_offsets_into_calendar_months():
    req = request()
    parsed = load.parse_fe(encoded(envelope(rows(req))), req)
    assert [(o.period_start, o.period_end) for o in parsed.observations][:2] == [
        (date(2021, 1, 1), date(2021, 1, 31)),
        (date(2021, 2, 1), date(2021, 2, 28)),
    ]
    assert [o.value for o in parsed.observations] == [100.25 + i for i in range(6)]
    assert parsed.excluded_outside_window == 0


def test_weekly_friday_rows_exclude_the_week_after_the_window():
    req = request(WEEKLY, end=date(2021, 1, 20))
    parsed = load.parse_fe(encoded(envelope(rows(req))), req)
    assert [o.period_end for o in parsed.observations] == [
        date(2021, 1, 1),
        date(2021, 1, 8),
        date(2021, 1, 15),
    ]
    # The first week starts before the window; only its end must be inside.
    assert parsed.observations[0].period_start == date(2020, 12, 26)
    assert parsed.excluded_outside_window == 1


def test_null_values_stay_missing_and_are_counted(lake):
    def mutate(data):
        data["items"][2][reviewed_series(MONTHLY).response_key] = None

    result = load.ingest_series(lake, MONTHLY, window(), retrieve=FakeSource(mutate=mutate))
    assert result.missing_values == 1
    assert read_series(lake.connection, result.series_id).observations[2].value is None


def _set(index, key, value):
    def mutate(data):
        data["items"][index][key] = value

    return mutate


KEY = reviewed_series(MONTHLY).response_key


@pytest.mark.parametrize(
    "mutate",
    [
        _set(0, KEY, "46,750"),  # Comma decimal would be a 1000x error.
        _set(0, KEY, "1,234.5"),  # Group separator.
        _set(0, KEY, 100.5),  # JSON number instead of the source string.
        _set(0, KEY, ""),
        _set(0, KEY, "NaN"),
        _set(0, KEY, "1e3"),
        _set(0, "F-1", "1.0"),  # Server formula column is not a published series.
        _set(0, "TP_KFE_TR10", "1.0"),  # Another series.
        _set(0, "Tarih", "01-2021"),
        _set(0, "Tarih", "2021-13"),
        _set(0, "UNIXTIME", {"$numberLong": "1609369200"}),  # Label and stamp disagree.
        _set(0, "UNIXTIME", 1609455600),
        lambda d: d["items"].pop(3),  # Gap in the calendar.
        lambda d: d["items"].insert(1, dict(d["items"][0])),  # Duplicate row.
        lambda d: d["items"].reverse(),
        lambda d: d.update(totalCount=99),
        lambda d: d.update(unexpected=True),
        lambda d: d.pop("items"),
    ],
)
def test_malformed_or_unexpected_responses_are_refused(lake, mutate):
    with pytest.raises(load.EvdsLoadError) as error:
        load.ingest_series(lake, MONTHLY, window(), retrieve=FakeSource(mutate=mutate))
    assert error.value.code is load.EvdsLoadCode.RESPONSE_INVALID
    assert counts(lake)[:2] == (0, 0)


@pytest.mark.parametrize(
    "payload",
    [b"not json", b'{"totalCount": 0, "totalCount": 0, "items": []}', b"[]", b"x" * (3 << 20)],
)
def test_invalid_json_and_budgets_are_refused(payload):
    with pytest.raises(load.EvdsLoadError):
        load.parse_fe(payload, request())


@pytest.mark.parametrize("change", ["yearweek", "off_anchor"])
def test_weekly_row_shape_and_anchor_are_enforced(change):
    req = request(WEEKLY, end=date(2021, 1, 20))
    items = rows(req)
    if change == "yearweek":
        items[0]["YEARWEEK"] = "week one"
    else:
        items[0] = row(WEEKLY, date(2020, 12, 31), "1.0")  # A Thursday.
    with pytest.raises(load.EvdsLoadError):
        load.parse_fe(encoded(envelope(items)), req)


def test_batch_is_idempotent_and_records_manifest_and_lineage(lake):
    source = FakeSource()
    first = load.ingest_series(lake, WEEKLY, window(end=date(2021, 3, 31)), retrieve=source)
    again = load.ingest_series(lake, WEEKLY, window(end=date(2021, 3, 31)), retrieve=source)
    assert (first.already_present, again.already_present) == (False, True)
    assert again.manifest_id == first.manifest_id and first.observations == 13
    manifest = json.loads(lake.read_artifact(first.manifest_id))
    assert manifest["series"] == WEEKLY and manifest["excluded_outside_window"] == 1
    assert manifest["transformation"] == load.TRANSFORMATION
    (raw,) = lake.lineage.sources_of(first.lineage_id)
    assert raw.attributes["artifact_id"] == manifest["raw_artifact_id"]
    semantics = read_series(lake.connection, first.series_id).semantics
    assert (semantics.frequency, semantics.anchor) == (Frequency.WEEKLY, WeeklyAnchor.FRIDAY)
    assert (semantics.observation, semantics.aggregation) == (StockFlow.RATE, Aggregation.AVERAGE)
    assert load.materialized_series(lake, WEEKLY, window(end=date(2021, 3, 31))) == first.__class__(
        first.series_id,
        first.manifest_id,
        first.lineage_id,
        13,
        0,
        1,
        True,
    )


@pytest.mark.parametrize("change", ["value", "window"])
def test_changed_history_or_window_refuses_and_preserves_prior(lake, change):
    load.ingest_series(lake, MONTHLY, window(), retrieve=FakeSource())
    before = lake.connection.execute("SELECT * FROM silver_observations ORDER BY 2").fetchall()
    if change == "value":
        attempt = (window(), FakeSource(mutate=_set(1, KEY, "999.5")))
    else:
        attempt = (window(end=date(2021, 7, 31)), FakeSource())
    with pytest.raises(load.EvdsLoadError) as error:
        load.ingest_series(lake, MONTHLY, attempt[0], retrieve=attempt[1])
    assert error.value.code is load.EvdsLoadCode.VERSION_CONFLICT
    assert lake.connection.execute("SELECT * FROM silver_observations ORDER BY 2").fetchall() == (
        before
    )


@pytest.mark.parametrize(
    "source",
    [
        FakeSource(failure=FetchCode.TRANSPORT_FAILURE),
        FakeSource(error=RuntimeError("secret remote detail")),
    ],
)
def test_retrieval_failures_are_sanitized_and_publish_nothing(lake, source):
    with pytest.raises(load.EvdsLoadError) as error:
        load.ingest_series(lake, MONTHLY, window(), retrieve=source)
    assert error.value.code is load.EvdsLoadCode.RETRIEVAL_FAILED
    assert "secret" not in str(error.value) and error.value.__cause__ is None
    assert counts(lake) == (0, 0, 0)


def test_mismatched_retrieval_identity_is_refused(lake):
    def wrong(req):
        other = request(end=date(2021, 5, 31))
        return FakeSource()(other).model_copy(
            update={"source_ref": other.fetch_request().source_ref}
        )

    with pytest.raises(load.EvdsLoadError) as error:
        load.ingest_series(lake, MONTHLY, window(), retrieve=wrong)
    assert error.value.code is load.EvdsLoadCode.RETRIEVAL_FAILED


def test_failure_after_registration_rolls_back(lake, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("disk")

    monkeypatch.setattr(type(lake), "append_observations", boom)
    with pytest.raises(load.EvdsLoadError) as error:
        load.ingest_series(lake, MONTHLY, window(), retrieve=FakeSource())
    assert error.value.code is load.EvdsLoadCode.MATERIALIZATION_FAILED
    assert counts(lake) == (0, 0, 0)


@pytest.mark.parametrize("corruption", ["value", "semantics", "window"])
def test_visibility_detects_corrupt_or_different_state(lake, corruption):
    load.ingest_series(lake, MONTHLY, window(), retrieve=FakeSource())
    checked = window()
    if corruption == "value":
        lake.connection.execute("UPDATE silver_observations SET value = 1 WHERE value > 102")
    elif corruption == "semantics":
        lake.connection.execute("UPDATE silver_series SET base_year = 2017")
    else:
        checked = window(end=date(2021, 5, 31))
    assert load.materialized_series(lake, MONTHLY, checked) is None


def test_prepared_series_reaches_query_and_answer_gate(lake):
    result = load.ingest_series(lake, MONTHLY, window(), retrieve=FakeSource())
    query = (
        "SELECT o.series_id,s.unit,s.scale,s.frequency,s.anchor,s.observation,"
        "o.period_start,o.period_end,o.value FROM silver_observations o"
        " JOIN silver_series s ON s.series_id=o.series_id WHERE o.period_end='2021-06-30'"
    )
    tool = make_lakehouse_tool(lake.connection, lineage=lake.lineage)
    output = tool.run(LakehouseArguments(sql=query), ExecutionContext(question="kfe")).output
    assert result.series_id == "EVDS:TP.KFE.TR"
    assert gate_answer("Endeks 105,25.", output.result, lake.connection).status == (
        AnswerStatus.ACCEPTED
    )
