"""A reviewed official series outside the prepared pool is fetched on first use (DEC-155).

No network: EVDS is a fake that returns the strict `fe` shape the real parser
accepts. What is pinned is the authority boundary as much as the success path:
only reviewed registry codes reach transport, one attempt per series per turn,
a small budget per turn, nothing when the operator has not enabled it, and the
same inspector verdict afterwards as for a prepared series.
"""

from datetime import date
from uuid import uuid4

import pytest
from test_catalog_continuation import CATALOG, proposal, seed_prepared
from test_evds_load import FakeSource

from kkb_agent.api.prepared import PreparedRunner, open_lakehouse
from kkb_agent.catalog.inspection import PreparedSeriesInspector
from kkb_agent.catalog.mappings import load_reviewed_snapshot
from kkb_agent.ingest.acquisition import (
    AcquiringInspector,
    AcquisitionCode,
    AcquisitionStore,
    OfficialSources,
    TurnAcquirer,
    acquisition_window,
    bddk_window,
)
from kkb_agent.llm import scripted

HOUSE_PRICES = "EVDS:TP.KFE.TR"
TODAY = date(2021, 6, 30)


@pytest.fixture
def pool(tmp_path):
    root = tmp_path / "prepared"
    seed_prepared(root)
    return root


@pytest.fixture
def lake(pool):
    with open_lakehouse(pool) as opened:
        yield opened


def test_a_reviewed_series_is_fetched_once_and_stored_through_the_strict_loader(lake):
    source = FakeSource()
    acquirer = TurnAcquirer(lake, TODAY, sources=OfficialSources(evds=source))

    first = acquirer.acquire(HOUSE_PRICES)
    again = acquirer.acquire(HOUSE_PRICES)

    assert first.code is AcquisitionCode.ACQUIRED and first.stored
    assert again is first and len(source.requests) == 1  # one attempt per series per turn
    assert (first.window_start, first.window_end) == (date(2011, 1, 1), TODAY)
    assert source.requests[0].code == "TP.KFE.TR"
    stored = lake.connection.execute(
        "SELECT count(*) FROM silver_observations WHERE series_id = ?", [HOUSE_PRICES]
    ).fetchone()[0]
    assert stored == first.observations == 126  # Jan 2011 .. Jun 2021


@pytest.mark.parametrize(
    "series_id",
    [
        "EVDS:TP.KFE.TR10",  # in the catalog, not in the reviewed transport registry
        "EVDS:TP.NOT.A.SERIES",
        "BDDK:selector:v1:" + "0" * 64,  # not a reviewed selector
        "https://evds3.tcmb.gov.tr/anything",
    ],
)
def test_nothing_outside_the_reviewed_registry_reaches_transport(lake, series_id):
    source = FakeSource()
    outcome = TurnAcquirer(lake, TODAY, sources=OfficialSources(evds=source)).acquire(series_id)
    assert outcome.code is AcquisitionCode.NO_REVIEWED_ROUTE and not outcome.stored
    assert source.requests == []


def test_a_turn_starts_at_most_its_budget_of_fetches(lake):
    source = FakeSource()
    acquirer = TurnAcquirer(lake, TODAY, sources=OfficialSources(evds=source), budget=1)
    assert acquirer.acquire("EVDS:TP.KFE.TR").stored
    refused = acquirer.acquire("EVDS:TP.TUKFIY2025.GENEL")
    assert refused.code is AcquisitionCode.BUDGET_EXHAUSTED
    assert len(source.requests) == 1
    # A series with no route does not spend the budget.
    assert acquirer.acquire("EVDS:TP.NOT.REVIEWED").code is AcquisitionCode.NO_REVIEWED_ROUTE


def test_a_failed_fetch_stores_nothing_and_says_so(lake):
    outcome = TurnAcquirer(
        lake, TODAY, sources=OfficialSources(evds=FakeSource(failure="timeout"))
    ).acquire(HOUSE_PRICES)
    assert outcome.code is AcquisitionCode.RETRIEVAL_FAILED and not outcome.stored
    assert (
        lake.connection.execute(
            "SELECT count(*) FROM silver_series WHERE series_id = ?", [HOUSE_PRICES]
        ).fetchone()[0]
        == 0
    )


def test_a_malformed_response_is_refused_not_stored(lake):
    def corrupt(data):
        data["items"][0]["Tarih"] = "not a date"

    outcome = TurnAcquirer(
        lake, TODAY, sources=OfficialSources(evds=FakeSource(mutate=corrupt))
    ).acquire(HOUSE_PRICES)
    assert outcome.code is AcquisitionCode.REFUSED and outcome.detail == "RESPONSE_INVALID"


def test_the_inspector_fetches_only_for_not_prepared_and_then_reinspects(lake):
    snapshot = load_reviewed_snapshot(CATALOG.read_bytes())
    source = FakeSource()
    inspector = AcquiringInspector(
        PreparedSeriesInspector(snapshot),
        TurnAcquirer(lake, TODAY, sources=OfficialSources(evds=source)),
    )

    assert inspector.inspect(lake.connection, HOUSE_PRICES).status == "consistent"
    # A catalog series with unknown semantics is refused before any fetch.
    assert inspector.inspect(lake.connection, "EVDS:TP.KFE.TR10").status == "unresolved_catalog"
    # An identity the catalog does not know is not fetched either.
    assert inspector.inspect(lake.connection, "EVDS:TP.GENENDEKS.X").status == "unknown_identity"
    assert len(source.requests) == 1


def test_the_window_is_the_operators_and_ends_on_a_whole_month():
    """Mid-month, the window ends at the previous month end: EVDS refuses a part month."""
    window = acquisition_window(date(2026, 9, 18))
    assert (window.start, window.end) == (date(2016, 1, 1), date(2026, 8, 31))
    assert acquisition_window(date(2026, 8, 31)).end == date(2026, 8, 31)
    assert acquisition_window(date(2026, 1, 5)).end == date(2025, 12, 31)


def test_an_acquisition_on_an_ordinary_mid_month_day_does_not_crash(lake):
    """The bug a month-end test date hid: a mid-month clock must still fetch."""
    source = FakeSource()
    outcome = TurnAcquirer(lake, date(2021, 7, 14), sources=OfficialSources(evds=source)).acquire(
        HOUSE_PRICES
    )
    assert outcome.code is AcquisitionCode.ACQUIRED, outcome
    assert outcome.window_end == date(2021, 6, 30)


def _calculate(start, end):
    return {
        "step_id": "a",
        "tool": "change_detection",
        "arguments": {
            "operation": "compare",
            "series_id": HOUSE_PRICES,
            "start": start,
            "end": end,
        },
    }


def _discover():
    return {"step_id": "d", "tool": "catalog_search", "arguments": {"query": "konut fiyat endeksi"}}


def test_a_served_question_on_a_series_outside_the_pool_is_answered(pool, tmp_path):
    """The planner finds the index in the catalog; the tool fetches it and computes."""
    from kkb_agent.api.store import ConversationStore

    source = FakeSource()
    store = ConversationStore(tmp_path / "conversations.sqlite")
    runner = PreparedRunner(
        scripted(
            proposal(_discover()),
            proposal(_calculate("2021-04-30", "2021-06-30")),
            "Nisan'dan Haziran 2021'e konut fiyat endeksi 2 puan arttı.",
        ),
        pool,
        tmp_path / "runtime",
        catalog_bytes=CATALOG.read_bytes(),
        store=store,
        official=OfficialSources(evds=source),
        clock=lambda: TODAY,
    )
    owner_id, token = store.create_owner()
    sid = uuid4().hex
    store.create_conversation(owner_id=owner_id, conversation_id=sid, token=token, title="Test")

    answer = runner(sid, uuid4().hex, "Nisan-Haziran 2021 konut fiyat endeksi ne kadar değişti?")

    assert answer.status.value == "accepted", answer
    assert len(source.requests) == 1
    assert "resmi kaynaktan bu turda edinildi" in answer.text
    assert any(
        "Actual acquisition provenance" in message.content for message in runner._provider.seen[-1]
    )
    events = store.events(store.runs(sid)[0].run_id)
    acquired = [event for event in events if event.name == "acquisition.acquired"]
    assert len(acquired) == 1
    assert acquired[0].attributes["series"] == HOUSE_PRICES
    assert acquired[0].attributes["observations"] == 126
    # The prepared seed itself is untouched: the series lives in this session's lake.
    with open_lakehouse(pool) as seed:
        assert (
            seed.connection.execute(
                "SELECT count(*) FROM silver_series WHERE series_id = ?", [HOUSE_PRICES]
            ).fetchone()[0]
            == 0
        )


def test_without_the_operator_switch_nothing_is_fetched(pool, tmp_path):
    source = FakeSource()
    runner = PreparedRunner(
        scripted(proposal(_discover()), proposal(_calculate("2021-04-30", "2021-06-30"))),
        pool,
        tmp_path / "runtime",
        catalog_bytes=CATALOG.read_bytes(),
        clock=lambda: TODAY,
    )
    answer = runner(uuid4().hex, uuid4().hex, "Nisan-Haziran 2021 konut fiyat endeksi?")
    assert answer.status.value == "abstained" and source.requests == []


@pytest.mark.parametrize("enabled", [True, False])
def test_readiness_reports_the_switch_and_nothing_else_changes(
    tmp_path, monkeypatch, capsys, enabled
):
    import json

    from test_prepared_api import set_config

    from kkb_agent.api import __main__ as api_cli

    set_config(monkeypatch)
    root = tmp_path.resolve() / "prepared"
    seed_prepared(root)
    command = ["--check", "--prepared-root", str(root), "--catalog", str(CATALOG)]
    if not enabled:
        command.append("--no-official-acquisition")

    assert api_cli.main(command) == 0
    assert json.loads(capsys.readouterr().out)["official_acquisition"] is enabled


def test_health_lists_the_capability_only_when_enabled():
    from kkb_agent.api.service import AnalysisService

    def runner(*args, **kwargs):  # never called: health does not run a turn
        raise AssertionError

    on = AnalysisService(runner, mode="scripted", official_acquisition=True)
    off = AnalysisService(runner, mode="scripted")
    try:
        assert "official_acquisition" in on.health().capabilities
        assert "official_acquisition" not in off.health().capabilities
    finally:
        on.close()
        off.close()


def test_a_reviewed_bddk_selector_is_fetched_month_by_month(lake):
    from test_bddk_monthly_load import FakeSource as MonthlySource

    from kkb_agent.ingest.acquisition import REVIEWED_SELECTORS

    source = MonthlySource()
    (tp,) = [sid for sid, sel in REVIEWED_SELECTORS.items() if sel.value_dimension == "TP"]
    outcome = TurnAcquirer(lake, TODAY, sources=OfficialSources(bddk=source)).acquire(tp)

    assert outcome.code is AcquisitionCode.ACQUIRED, outcome
    window = bddk_window(TODAY)
    # From the first prepared month (2021-01) to three months before the clock's month:
    # 2021-03 for 2021-06-30. Two fixed years answered "2021-2025" with half the years.
    assert (window.start.year, window.start.month) == (2021, 1)
    assert (window.end.year, window.end.month) == (2021, 3)
    assert len(source.requests) == len(window.periods()) == 3
    assert outcome.window_end == date(2021, 3, 31) and outcome.observations == 3
    later = bddk_window(date(2026, 9, 19))
    assert (later.start.year, later.start.month, later.end.year, later.end.month) == (
        2021,
        1,
        2026,
        6,
    )
    assert len(later.periods()) == 66


def test_fetched_responses_are_kept_for_the_next_conversation(tmp_path, lake):
    """A second lake, like a new conversation, is rebuilt from kept bytes, not refetched."""
    from kkb_agent.lakehouse import open_lakehouse

    store = AcquisitionStore(tmp_path / "acquired")
    source = FakeSource()
    first = TurnAcquirer(lake, TODAY, sources=OfficialSources(evds=source, store=store))
    assert first.acquire(HOUSE_PRICES).code is AcquisitionCode.ACQUIRED
    assert len(source.requests) == 1

    with open_lakehouse(tmp_path / "another") as other:
        again = TurnAcquirer(other, TODAY, sources=OfficialSources(evds=source, store=store))
        replayed = again.acquire(HOUSE_PRICES)
        assert replayed.code is AcquisitionCode.ACQUIRED and replayed.from_store
        assert len(source.requests) == 1  # nothing asked of the source the second time
        assert replayed.observations == 126

    log = store.acquisitions()
    assert log[HOUSE_PRICES]["observations"] == 126 and log[HOUSE_PRICES]["fetched_at"]
    # A new month is a new window: the kept bytes do not answer it, the source does.
    with open_lakehouse(tmp_path / "next_month") as later:
        TurnAcquirer(
            later, date(2021, 7, 31), sources=OfficialSources(evds=source, store=store)
        ).acquire(HOUSE_PRICES)
    assert len(source.requests) == 2


def test_a_failed_fetch_is_not_kept(tmp_path, lake):
    store = AcquisitionStore(tmp_path / "acquired")
    failing = FakeSource(failure="timeout")
    TurnAcquirer(lake, TODAY, sources=OfficialSources(evds=failing, store=store)).acquire(
        HOUSE_PRICES
    )
    assert store.acquisitions() == {}
    assert not [p for p in (tmp_path / "acquired").iterdir() if p.name != "acquisitions.json"]
