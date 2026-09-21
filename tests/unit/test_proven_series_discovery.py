"""A series the catalog already returned in this conversation need not be found again.

Required discovery exists so the catalog, not the planner, decides which series an
identity refers to. It made the planner search on every turn, even for an identity
the catalog had returned minutes earlier in the same conversation, which costs a
whole planning round trip and buys no authority.

These tests pin what the relaxation may and may not do. The dangerous direction is
a plan naming an identity nobody vouched for, so most of what follows checks that
such a plan is still refused.
"""

from datetime import date
from pathlib import Path

import pytest
from pydantic import BaseModel
from test_catalog_continuation import TOTAL, rig  # noqa: F401 - fixture reused here

from kkb_agent.agent.discovery import (
    REQUIRED_DISCOVERY_INSTRUCTIONS,
    needs_series_discovery,
    proven_identities,
    required_discovery_instructions,
    validate_discovery_phase,
)
from kkb_agent.agent.executor import (
    ExecutionContext,
    ExecutionOutcome,
    PlanRejected,
    ToolResult,
    ToolStatus,
    ValidatedPlan,
    ValidatedStep,
)
from kkb_agent.agent.plan import PlanStep
from kkb_agent.catalog.search import CatalogSearchOutput
from kkb_agent.core import declared_series_identities
from kkb_agent.tools import make_catalog_search_tool
from kkb_agent.tools.anomaly import AnomalyArguments
from kkb_agent.tools.change_detection import ChangeDetectionArguments
from kkb_agent.tools.lakehouse import LakehouseArguments
from kkb_agent.tools.promotion import PromoteSeriesArguments
from kkb_agent.tools.table_transform import TableTransformArguments

OTHER = "EVDS:TP.TUKFIY2025.GENEL"


CATALOG = Path(__file__).parents[2] / "docs/catalog/prepared_v2.json"


def real_catalog_output():
    """A genuine search result, so tests can vary the tool name and status around it."""
    spec = make_catalog_search_tool(snapshot_bytes=CATALOG.read_bytes())
    output = spec.run(
        spec.arguments.model_validate({"query": "toplam konut kredisi"}),
        ExecutionContext("q"),
    ).output
    assert output.candidates, "the fixture catalog must return candidates"
    return output


def step(tool, arguments, step_id="a"):
    raw = arguments.model_dump(mode="json")
    return ValidatedStep(PlanStep(step_id=step_id, tool=tool, arguments=raw), arguments)


def plan_of(*steps):
    return ValidatedPlan("q", tuple(steps))


def change(series_id=TOTAL):
    return ChangeDetectionArguments.model_validate(
        {
            "operation": "compare",
            "series_id": series_id,
            "start": "2025-01-31",
            "end": "2025-12-31",
        }
    )


def add_series(series_id=TOTAL):
    return TableTransformArguments.model_validate(
        {"operation": "add_series", "source": "analiz_1", "series_id": series_id}
    )


def promotion():
    return PromoteSeriesArguments(
        title="Şirket geliri", unit="TL", scale="million", meaning="monthly_total"
    )


def deflate(index_series_id=OTHER):
    return TableTransformArguments.model_validate(
        {
            "operation": "deflate",
            "source": "analiz_1",
            "column": "amount",
            "index_series_id": index_series_id,
            "reference_period": date(2025, 12, 31),
        }
    )


# --- the contract declares which fields are identities -----------------------


def test_argument_contract_reports_the_identities_a_step_names():
    assert declared_series_identities(change()) == frozenset({TOTAL})
    assert declared_series_identities(deflate()) == frozenset({OTHER})
    assert declared_series_identities(add_series()) == frozenset({TOTAL})


def test_sql_arguments_report_unknown_rather_than_empty():
    """SQL can name any series, so its absence of marked fields must not read as none."""
    arguments = LakehouseArguments.model_validate({"sql": "select 1 from silver_observations"})
    assert declared_series_identities(arguments) is None


def test_a_step_with_no_identity_field_reports_an_empty_set_not_unknown():
    arguments = TableTransformArguments.model_validate(
        {"operation": "filter", "source": "analiz_1", "start_period": date(2021, 1, 31)}
    )
    assert declared_series_identities(arguments) == frozenset()


# --- what counts as proven ---------------------------------------------------


def test_only_a_successful_catalog_search_proves_an_identity():
    empty = CatalogSearchOutput(
        status="NO_MATCH",
        total_candidates=0,
        truncated=False,
        clarification_required=False,
        excluded_archived_count=0,
        snapshot_version="v3",
        snapshot_sha256="0" * 64,
    )
    failed = ToolResult(
        ToolStatus.FAILURE,
        step_id="d",
        tool="catalog_search",
        output=empty,
        error_category="no_match",
    )
    assert proven_identities(ExecutionOutcome((failed,), True)) == frozenset()


def test_a_non_catalog_result_proves_nothing_even_when_it_names_a_series():
    """An analysis result mentions identities constantly; none of that is authority."""
    analysis = ToolResult(
        ToolStatus.SUCCESS,
        step_id="a",
        tool="change_detection",
        output=f"computed over {TOTAL}",
    )
    assert proven_identities(ExecutionOutcome((analysis,), True)) == frozenset()


# --- the admission rule ------------------------------------------------------


def test_a_proven_identity_no_longer_needs_a_second_search():
    assert needs_series_discovery(plan_of(step("change_detection", change())))
    assert not needs_series_discovery(
        plan_of(step("change_detection", change())), frozenset({TOTAL})
    )


def test_an_unproven_identity_is_still_refused(rig):  # noqa: F811
    """The whole point of the rule: the planner may not name a series on its own."""
    plan = plan_of(step("change_detection", change("BDDK:invented:by:the:model")))
    with pytest.raises(PlanRejected, match="catalog_search phase"):
        validate_discovery_phase(
            plan,
            continuation=False,
            require_series_discovery=True,
            proven_series=frozenset({TOTAL}),
        )


def test_document_promotion_needs_no_catalog_but_mixed_unproven_read_does():
    offer = step("promote_series", promotion())
    validate_discovery_phase(plan_of(offer), continuation=False, require_series_discovery=True)
    with pytest.raises(PlanRejected, match="Continuation permits"):
        validate_discovery_phase(plan_of(offer), continuation=True, require_series_discovery=True)

    mixed = plan_of(offer, step("change_detection", change(), step_id="b"))
    with pytest.raises(PlanRejected, match="catalog_search phase"):
        validate_discovery_phase(mixed, continuation=False, require_series_discovery=True)


def test_one_unproven_identity_among_proven_ones_still_requires_discovery():
    plan = plan_of(
        step("change_detection", change(TOTAL), step_id="a"),
        step("table_transform", deflate(OTHER), step_id="b"),
    )
    assert needs_series_discovery(plan, frozenset({TOTAL}))
    assert not needs_series_discovery(plan, frozenset({TOTAL, OTHER}))


def test_a_sql_step_never_qualifies_however_much_is_proven():
    """SQL could read a series nobody proved, so proof of others cannot admit it."""
    arguments = LakehouseArguments.model_validate({"sql": "select * from silver_observations"})
    plan = plan_of(step("lakehouse", arguments))
    assert needs_series_discovery(plan, frozenset({TOTAL, OTHER}))


def test_proof_from_another_conversation_does_not_travel():
    """The caller passes one conversation's set; an empty set must refuse, not admit."""
    assert needs_series_discovery(plan_of(step("change_detection", change())), frozenset())


def test_an_anomaly_step_follows_the_same_rule():
    arguments = AnomalyArguments.model_validate({"series_id": TOTAL})
    plan = plan_of(step("anomaly", arguments))
    assert needs_series_discovery(plan)
    assert not needs_series_discovery(plan, frozenset({TOTAL}))


def test_validate_admits_a_fully_proven_plan_before_any_tool_runs():
    validate_discovery_phase(
        plan_of(step("change_detection", change())),
        continuation=False,
        require_series_discovery=True,
        proven_series=frozenset({TOTAL}),
    )


# --- the instruction the planner reads ---------------------------------------


def test_instructions_stay_unchanged_when_nothing_is_proven():
    assert required_discovery_instructions(frozenset()) == REQUIRED_DISCOVERY_INSTRUCTIONS
    assert "promote_series offer for an admitted document" in REQUIRED_DISCOVERY_INSTRUCTIONS


def test_instructions_name_the_proven_identities_and_drop_the_contradiction():
    text = required_discovery_instructions(frozenset({TOTAL}), {TOTAL: "Toplam konut kredisi"})
    assert TOTAL in text and "Toplam konut kredisi" in text
    # The old rule ordered a search "even if a reviewed series identity is already
    # visible", which contradicts admitting exactly that plan.
    assert "even if a reviewed series identity is already visible" not in text
    assert "Read them directly; do not search for them again" in text
    assert "MUST" not in text  # one policy, said without an order that contradicts it
    assert "promote_series offer for an admitted document" in text


def test_a_failed_catalog_search_proves_nothing_even_with_candidates_attached():
    """Status is checked on its own: real candidates must not smuggle in authority."""
    failed = ToolResult(
        ToolStatus.FAILURE,
        step_id="d",
        tool="catalog_search",
        output=real_catalog_output(),
        error_category="no_match",
    )
    assert proven_identities(ExecutionOutcome((failed,), True)) == frozenset()


def test_only_the_catalog_tool_proves_even_with_a_catalog_shaped_output():
    """The tool name is checked on its own: another tool may not return this shape."""
    impostor = ToolResult(
        ToolStatus.SUCCESS,
        step_id="a",
        tool="web_search",
        output=real_catalog_output(),
    )
    assert proven_identities(ExecutionOutcome((impostor,), True)) == frozenset()


def test_the_catalog_tool_does_prove_its_own_successful_candidates():
    """The control for the two tests above: the honest case must still work."""
    output = real_catalog_output()
    result = ToolResult(ToolStatus.SUCCESS, step_id="d", tool="catalog_search", output=output)
    proven = proven_identities(ExecutionOutcome((result,), True))
    assert proven == {candidate.series.record.series_id for candidate in output.candidates}


def test_a_step_naming_no_identity_is_not_admitted_by_an_empty_set():
    """Naming nothing is not proof of anything; only a conservative refusal is safe."""
    arguments = LakehouseArguments.model_validate({"sql": "select 1"})
    assert needs_series_discovery(plan_of(step("lakehouse", arguments)), frozenset({TOTAL}))

    class Bare(BaseModel):
        note: str = ""

    bare = plan_of(step("some_future_tool", Bare()))
    assert declared_series_identities(Bare()) == frozenset()
    assert needs_series_discovery(bare, frozenset({TOTAL}))


def test_the_rejection_names_the_unsearched_series_and_asks_for_every_measure():
    """Live E2 (2026-09-19): told only that new series need a search, the planner searched for
    one of the two measures it needed and then called the other one missing."""
    plan = plan_of(
        step("change_detection", change(TOTAL), step_id="a"),
        step("table_transform", deflate(OTHER), step_id="b"),
    )
    with pytest.raises(PlanRejected) as refused:
        validate_discovery_phase(
            plan,
            continuation=False,
            require_series_discovery=True,
            proven_series=frozenset({TOTAL}),
        )
    message = str(refused.value)
    assert OTHER in message and TOTAL not in message
    assert "one query for EACH measure" in message


def test_a_web_search_plan_needs_no_catalogue_discovery():
    """Live W1 (2026-09-19): the rule refused every web_search plan, so the tool never ran."""
    from kkb_agent.tools.web_search import SearchRequest

    plan = plan_of(step("web_search", SearchRequest(query="TCMB faiz kararı")))
    assert not needs_series_discovery(plan)
    validate_discovery_phase(
        plan, continuation=False, require_series_discovery=True, proven_series=frozenset()
    )


def test_sql_over_this_conversations_published_tables_needs_no_discovery():
    """Live B2 (2026-09-20): asking for the mean of a table the agent had just
    published was refused with "New series require a catalog_search phase", and
    the round trip cost 111 s. Those rows are already proven; series tables are
    still behind the rule."""
    from kkb_agent.tools.lakehouse import LakehouseArguments

    published = plan_of(
        step(
            "lakehouse",
            LakehouseArguments(
                sql=(
                    "SELECT AVG(value) FROM gold_cells WHERE result_name = 'analiz_6'"
                    " AND column_label = 'EVDS:TP.KTF12 monthly average'"
                ),
                purpose="Yayımlanmış tablonun ortalaması",
            ),
        )
    )
    assert not needs_series_discovery(published)
    validate_discovery_phase(
        published, continuation=False, require_series_discovery=True, proven_series=frozenset()
    )

    series = plan_of(
        step(
            "lakehouse",
            LakehouseArguments(
                sql="SELECT * FROM silver_observations LIMIT 5",
                purpose="Seri verisi",
            ),
        )
    )
    assert needs_series_discovery(series)


# --- what the catalogue lists needs no search to be read --------------------------------------


def test_an_identity_the_catalogue_lists_is_read_without_a_search_of_its_own():
    # 13 of 22 stored plan rejections were "New series require a catalog_search phase": the
    # planner named a real catalogue ID and paid two more model calls to be allowed to
    # read it. The catalogue vouches for what it lists; the inspector checks it when read.
    for continuation in (False, True):
        validate_discovery_phase(
            plan_of(step("change_detection", change()), step("table_transform", deflate(), "b")),
            continuation=continuation,
            require_series_discovery=True,
            known_series=frozenset({TOTAL, OTHER}),
        )


def test_an_identity_the_catalogue_does_not_hold_is_refused_by_name():
    with pytest.raises(PlanRejected) as refusal:
        validate_discovery_phase(
            plan_of(step("change_detection", change("EVDS:TP.UYDURMA"))),
            continuation=False,
            require_series_discovery=True,
            known_series=frozenset({TOTAL}),
        )
    assert "EVDS:TP.UYDURMA" in str(refusal.value) and "catalog_search" in str(refusal.value)
    # In a continuation with no search left, the refusal does not offer one.
    with pytest.raises(PlanRejected) as final:
        validate_discovery_phase(
            plan_of(step("change_detection", change("EVDS:TP.UYDURMA"))),
            continuation=True,
            require_series_discovery=True,
            known_series=frozenset({TOTAL}),
        )
    assert "EVDS:TP.UYDURMA" in str(final.value) and "plan catalog_search" not in str(final.value)
