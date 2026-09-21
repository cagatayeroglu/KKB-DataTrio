"""What the planner is given over a long conversation, and what it must not be given.

A conversation accumulates tables. Putting their values in the prompt would make
context grow with the data and would let a model restate a figure it never
computed. What the planner receives instead is a reference: each table's name,
what produced it, the period it covers and its column labels. The values stay in
the workspace, and a step that names a table reads them there.

These turns pin nothing and state no continuation: the planner picks the table,
including an older one, and must still land on the right one.
"""

import json
from datetime import date
from uuid import uuid4

import pytest
from test_catalog_continuation import CATALOG, TOTAL, proposal, seed_prepared
from test_series_inspection import CPI, SQL

from kkb_agent.agent import Session, ToolRegistry, Workspace
from kkb_agent.api.prepared import PreparedRunner, open_lakehouse
from kkb_agent.catalog.mappings import load_reviewed_snapshot
from kkb_agent.core import SourceRef
from kkb_agent.lakehouse import Observation, SeriesSemantics
from kkb_agent.llm import scripted
from kkb_agent.llm.provider import Role

#: The figures the tables hold; none of them may appear in a planner prompt.
CREDIT_VALUES = (100.0, 120.0, 150.0)
CPI_VALUES = (100.0, 110.0, 120.0)


def test_the_conversation_is_shown_whatever_the_next_question_looks_like():
    """Which turns are a follow-up is the planner's reading, not a word list's.

    A word list decided this until 2026-09-22 ("bu tablo", "önceki cevap", "aynı seri").
    It let "grafiği çiz bi" through as a question about nothing: four words, no
    conversation, answered as if nothing had been asked before. The block is six turns of
    questions and answer text, about 500 bytes beside a 42 KB prompt, and its header says
    what it is for - resolving a reference - and that its figures are not evidence.
    """
    previous = (("İstanbul konut kredilerini göster.", "İstanbul tablosu hazır."),)
    for question in ("2021-2025 Türkiye konut kredisi bakiyesi nedir?", "grafiği çiz bi"):
        provider = scripted(proposal(clarification="unsupported_request"))
        Session(provider, ToolRegistry(), history=previous).plan(question)
        shown = [
            item.content
            for item in provider.seen[0]
            if item.content.startswith("Earlier turns of this conversation")
        ]
        assert len(shown) == 1, question
        assert "İstanbul" in shown[0]
        assert "figures in them are not new evidence" in shown[0]

    # A conversation that has not started shows nothing.
    fresh = scripted(proposal(clarification="unsupported_request"))
    Session(fresh, ToolRegistry()).plan("İstanbul konut kredilerini göster.")
    assert not any(
        item.content.startswith("Earlier turns of this conversation") for item in fresh.seen[0]
    )


@pytest.fixture
def pool(tmp_path):
    root = tmp_path / "prepared"
    seed_prepared(root)
    return root


def table(step_id="a"):
    return {"step_id": step_id, "tool": "lakehouse", "arguments": {"sql": SQL}}


def add_index(source, step_id="b"):
    return {
        "step_id": step_id,
        "tool": "table_transform",
        "arguments": {"operation": "add_series", "source": source, "series_id": CPI},
    }


def deflate(source, step_id="d"):
    return {
        "step_id": step_id,
        "tool": "table_transform",
        "arguments": {
            "operation": "deflate",
            "source": source,
            "column": TOTAL,
            "index_series_id": CPI,
            "reference_period": "2026-06-30",
        },
    }


def reply(text):
    return json.dumps({"question": "q", "steps": [], "clarification": None, "reply": text})


def with_index(pool):
    """The prepared pool plus the index a later turn adds to a published table."""
    from test_catalog_continuation import NOW

    record = next(
        item.record
        for item in load_reviewed_snapshot(CATALOG.read_bytes()).series
        if item.record.series_id == CPI
    )
    with open_lakehouse(pool) as lake:
        artifact = lake.record_artifact(
            b"synthetic cpi 100 110 120",
            source=SourceRef(source_id="fixture", source_type="fixture", locator="opaque:fixture"),
            media_type="text/plain",
            recorded_at=NOW,
        )
        lake.register_series(
            CPI,
            title="Synthetic CPI",
            artifact_id=artifact.artifact_id,
            semantics=SeriesSemantics(
                unit=record.unit,
                scale=record.scale,
                frequency=record.frequency,
                observation=record.stock_flow,
                cumulative=record.cumulative,
                aggregation=record.aggregation.default,
                base_year=record.base_year,
            ),
        )
        lake.append_observations(
            CPI,
            [
                Observation(date(2026, month, 1), date(2026, month, last), value)
                for month, last, value in zip((4, 5, 6), (30, 31, 30), CPI_VALUES, strict=True)
            ],
        )


def workspace_prompts(provider):
    """The earlier-results message of every planning call, in order."""
    found = []
    for messages in provider.seen:
        for message in messages:
            if message.role is Role.SYSTEM and message.content.startswith(
                "Results published in earlier turns"
            ):
                found.append(message.content)
    return found


def test_five_turns_reach_the_right_table_through_references_not_values(pool, tmp_path):
    """Two tables, a chat message between them, then a step on the older table."""
    with_index(pool)
    provider = scripted(
        # 1: a table from the prepared pool.
        proposal(table()),
        "Konut kredisi tablosu hazır.",
        # 2: the index added to that table.
        proposal(add_index("analiz_1")),
        "Tabloya TÜFE eklendi.",
        # 3: small talk in the middle; no tool, no publication.
        reply("Tablo aylık bakiyeyi ve TÜFE'yi yan yana gösteriyor."),
        # 4: a second, independent table.
        proposal(table("c")),
        "İkinci tablo hazır.",
        # 5: a step on analiz_2, which is no longer the newest table.
        proposal(deflate("analiz_2")),
        "İstenen tablo enflasyondan arındırıldı.",
    )
    runner = PreparedRunner(
        provider, pool, tmp_path / "runtime", catalog_bytes=CATALOG.read_bytes()
    )
    sid = uuid4().hex

    first = runner(sid, uuid4().hex, "Konut kredisi tablosunu getir.")
    second = runner(sid, uuid4().hex, "Bu tabloya TÜFE'yi ekle.")
    third = runner(sid, uuid4().hex, "Teşekkürler, tablo ne anlatıyor?")
    fourth = runner(sid, uuid4().hex, "Konut kredisi tablosunu bir daha getir.")
    fifth = runner(sid, uuid4().hex, "İkinci analizdeki tabloyu TÜFE ile reelleştir.")

    assert [turn.status.value for turn in (first, second, fourth, fifth)] == ["accepted"] * 4
    assert third.status.value == "accepted" and third.result is None  # a reply publishes nothing

    with open_lakehouse(runner.run_root / sid / "lake") as lake:
        workspace = Workspace.open(lake.connection, sid)
        # Names follow turn numbers, so the chat turn leaves a gap instead of
        # renumbering tables that earlier answers already refer to.
        assert workspace.names() == ["analiz_1", "analiz_2", "analiz_4", "analiz_5"]
        assert workspace.value_of("analiz_2").digest() == second.result.version

    # The fifth turn reached back past the newest table to the one it named: its
    # nominal and index columns are analiz_2's, with the real column derived from them.
    values = [cell.value for cell in fifth.result.cells]
    assert values[: len(CREDIT_VALUES)] == list(CREDIT_VALUES)
    assert CPI_VALUES[1] in values  # the index came along, not a fresh read
    real = values[-len(CREDIT_VALUES) :]
    assert real[0] == pytest.approx(120.0) and real[-1] == pytest.approx(150.0)


def test_the_planner_is_given_names_and_coverage_but_never_the_figures(pool, tmp_path):
    with_index(pool)
    provider = scripted(
        proposal(table()),
        "Konut kredisi tablosu hazır.",
        proposal(add_index("analiz_1")),
        "Tabloya TÜFE eklendi.",
        proposal(table("c")),
        "Üçüncü tablo hazır.",
    )
    runner = PreparedRunner(
        provider, pool, tmp_path / "runtime", catalog_bytes=CATALOG.read_bytes()
    )
    sid = uuid4().hex
    for question in (
        "Konut kredisi tablosunu getir.",
        "Bu tabloya TÜFE'yi ekle.",
        "Bir tablo daha getir.",
    ):
        assert runner(sid, uuid4().hex, question).status.value == "accepted"

    prompts = workspace_prompts(provider)
    # Every question after the first is told which tables exist: names and labels, never
    # figures. A word list used to decide whether the question referred to one; "Tabloya
    # konut fiyat endeksini de ekle" matched nothing in it, the planner invented a table
    # name, and the jury's third turn lost sixteen minutes to the refusal (live 2026-09-21).
    assert len(prompts) == 2
    last = prompts[0]
    assert "analiz_1" in last and "analiz_2" not in last
    assert "analiz_2" in prompts[1]
    assert "coverage 2026-04-01..2026-06-30" in last
    assert "column labels:" in last
    # No published figure is in the prompt, in any shape a model could read. 100 is
    # excluded: it is the index's base year in the reviewed series name, not a value.
    for value in (120.0, 150.0, 110.0):
        for shape in (f"{value:.1f}", f"{value:.0f}"):
            assert shape not in last, shape
    # A reference costs a line per table, so the prompt grows with tables, not rows.
    assert len(last) < 1200


def test_context_stays_bounded_as_the_conversation_gets_long(pool, tmp_path):
    """Ten turns: history is the last six questions and shown answers, nothing more."""
    from kkb_agent.agent.loop import HISTORY_HEADER, MAX_HISTORY_TURNS

    provider = scripted(*[item for _ in range(10) for item in (reply("Buyurun."),)])
    runner = PreparedRunner(
        provider, pool, tmp_path / "runtime", catalog_bytes=CATALOG.read_bytes()
    )
    sid = uuid4().hex
    questions = [f"Önceki cevap için soru {index}: nasıl gidiyor?" for index in range(10)]
    for question in questions:
        assert runner(sid, uuid4().hex, question).status.value == "accepted"

    histories = [
        message.content
        for messages in provider.seen
        for message in messages
        if message.content.startswith(HISTORY_HEADER)
    ]
    assert len(histories) == 9  # every turn after the first carries one
    final = histories[-1]
    assert final.count("User: ") == MAX_HISTORY_TURNS
    assert questions[0] not in final and questions[-2] in final


def test_a_long_conversation_keeps_every_table_reachable_within_a_budget(
    pool, tmp_path, monkeypatch
):
    """Over budget, older tables keep a one-line entry; none disappears."""
    from kkb_agent.agent import loop as loop_module

    provider = scripted(*[item for _ in range(4) for item in (proposal(table()), "Tablo hazır.")])
    runner = PreparedRunner(
        provider, pool, tmp_path / "runtime", catalog_bytes=CATALOG.read_bytes()
    )
    sid = uuid4().hex
    for _ in range(4):
        assert runner(sid, uuid4().hex, "Konut kredisi tablosunu getir.").status.value == "accepted"

    with open_lakehouse(runner.run_root / sid / "lake") as lake:
        workspace = Workspace.open(lake.connection, sid)
        full = loop_module.workspace_prompt(workspace)
        assert full is not None and "labels omitted" not in full
        one_table = max(len(line) for line in full.splitlines()[1:]) + 1
        monkeypatch.setattr(loop_module, "MAX_WORKSPACE_PROMPT_CHARS", one_table * 2)
        tight = loop_module.workspace_prompt(workspace)

    assert tight is not None and len(tight) < len(full)
    for name in ("analiz_1", "analiz_2", "analiz_3", "analiz_4"):
        assert name in tight  # every table is still named
    assert "analiz_4: produced by" in tight and "column labels:" in tight  # newest in full
    assert "analiz_1: produced by" in tight and "labels omitted" in tight
    assert "still usable by name" in tight
    # Publication order is kept, so "the first table" still means analiz_1.
    assert tight.index("analiz_1") < tight.index("analiz_4")


def test_an_earlier_table_is_described_by_its_reviewed_series_name(pool, tmp_path):
    """Live trace 2026-09-18: the outline named a table only by a selector hash."""
    provider = scripted(proposal(table()), "Tablo hazır.", proposal(table("b")), "Tablo hazır.")
    runner = PreparedRunner(
        provider, pool, tmp_path / "runtime", catalog_bytes=CATALOG.read_bytes()
    )
    sid = uuid4().hex
    for question in ("Konut kredisi tablosunu getir.", "Önceki tabloyu bir daha getir."):
        assert runner(sid, uuid4().hex, question).status.value == "accepted"

    (outline,) = workspace_prompts(provider)
    # Generated from the catalog record: its TOTAL label tells the components apart.
    assert (
        f"{TOTAL} means: BDDK: Tüketici Kredileri - Konut [Aylık Bülten, Sektör, TOTAL" in outline
    )


def test_a_table_request_gives_the_writer_the_table(pool, tmp_path):
    """Three live traces, three failures from the same cause.

    2026-09-18: with every value tabled and none listed, the writer wrote "this
    question was not covered" beside a 24-row table. 2026-09-20: told instead
    that the table itself was the answer, it wrote only that a table exists,
    which the reader was already looking at. 2026-09-21: given a short table as
    its two ends, it wrote that the months between them were not shown in the
    result. A table short enough to read is now given whole.
    """
    provider = scripted(proposal(table()), "Tablo hazır.")
    runner = PreparedRunner(
        provider, pool, tmp_path / "runtime", catalog_bytes=CATALOG.read_bytes()
    )
    assert runner(uuid4().hex, uuid4().hex, "Tabloyu getir.").status.value == "accepted"

    writer = provider.seen[-1]
    results = next(m.content for m in writer if m.role is Role.SYSTEM and "Analysis" in m.content)
    assert "Every one of its values is listed below." in results
    assert "an answer that only says a table exists tells them nothing" in results
    # Every row is there to quote, not only the two ends.
    quoted = [line for line in results.splitlines() if line.startswith("- ")]
    assert len(quoted) == 3 and all("display" in line for line in quoted)
