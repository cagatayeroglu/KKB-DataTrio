"""Mend what a plan says about itself, instead of spending a model call on it.

A plan is refused when it could run something nobody asked for. It used to be refused as
well for bookkeeping the harness can read off the plan: a step that names another step as
its table and leaves it out of `depends_on`, an ordering edge between two catalogue
searches, a step ID an earlier phase of the turn had used. Each refusal is a whole planner
call, and on the served model that is minutes (measured 2026-09-21: eight to thirty-three
minutes a call, 91% of it reasoning). None of these changes what the plan computes, so they
are settled here and recorded in the trace.

What is never mended: an unknown tool, arguments a tool does not accept, a table that does
not exist, a cycle. Those say the plan is about something else, and the planner is told.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping

from pydantic import BaseModel, JsonValue

from kkb_agent.agent.plan import AnalyticalPlan, PlanStep
from kkb_agent.agent.registry import ArgumentsRejected, RegistryError, ToolRegistry
from kkb_agent.core.identity import declared_series_identities

#: The argument fields that name another step or a published table (registry `TableInput`).
REFERENCE_FIELDS = ("source", "other", "input_step")
MAX_IDENTIFIER = 64


def _namespaced(arguments: BaseModel, known: Collection[str]) -> dict[str, str]:
    """Identities the plan names without their namespace, and what the catalogue calls them.

    A catalogue identity carries the provider that issued it: `USER:kart_harcamasi.v1`,
    `EVDS:TP.KTF12`. A planner that writes the rest of one has named a series exactly, and
    exactly one series; refusing it as "not in the catalogue" cost a whole planner call
    over a prefix (live 2026-09-22: the reader asked for USER:promotion_test_konut_
    bakiyesi.v1 by its full identity and the plan came back without the USER:). Mended only
    when the tail matches one identity: two would be a choice, and choosing is the
    planner's.
    """
    declared = declared_series_identities(arguments)
    if not declared or not known:
        return {}
    mended: dict[str, str] = {}
    for identity in declared:
        if identity in known:
            continue
        matches = [item for item in known if item.endswith(f":{identity}")]
        if len(matches) == 1:
            mended[identity] = matches[0]
    return mended


def _rewritten(value: JsonValue, mapping: Mapping[str, str]) -> JsonValue:
    """`value` with every string the mapping names replaced, however deeply it is nested."""
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, list):
        return [_rewritten(item, mapping) for item in value]
    if isinstance(value, dict):
        return {key: _rewritten(item, mapping) for key, item in value.items()}
    return value


def _fresh(step_id: str, taken: set[str]) -> str:
    number = 2
    while True:
        suffix = f"_{number}"
        candidate = step_id[: MAX_IDENTIFIER - len(suffix)] + suffix
        if candidate not in taken:
            return candidate
        number += 1


def heal_plan(
    plan: AnalyticalPlan,
    registry: ToolRegistry,
    *,
    used_ids: Collection[str] = (),
    known_tables: Collection[str] = (),
    known_series: Collection[str] = (),
) -> tuple[AnalyticalPlan, tuple[str, ...]]:
    """`plan` with its own bookkeeping completed, and one note per thing that was mended."""
    ids = [step.step_id for step in plan.steps]
    if not ids or len(set(ids)) != len(ids):
        return plan, ()  # Two steps of one ID: a reference to it has no single meaning.
    notes: list[str] = []
    taken = {*ids, *used_ids, *known_tables}
    renamed: dict[str, str] = {}
    for step_id in ids:
        # A published table of the same name keeps the name: a reference to it may mean
        # either, and only the planner knows which.
        if step_id in used_ids and step_id not in known_tables:
            renamed[step_id] = _fresh(step_id, taken)
            taken.add(renamed[step_id])
            notes.append(f"step {step_id!r} renamed {renamed[step_id]!r}: the ID was used earlier")
    present = {renamed.get(step_id, step_id) for step_id in ids}
    steps: list[PlanStep] = []
    for step in plan.steps:
        step_id = renamed.get(step.step_id, step.step_id)
        arguments: dict[str, JsonValue] = {
            key: renamed.get(value, value)
            if key in REFERENCE_FIELDS and isinstance(value, str)
            else value
            for key, value in step.arguments.items()
        }
        depends: list[str] = []
        for name in (renamed.get(item, item) for item in step.depends_on):
            if name == step_id or name not in present:
                notes.append(
                    f"step {step_id!r}: dropped the edge to {name!r}, which orders nothing"
                )
            elif name not in depends:
                depends.append(name)
        try:
            spec = registry.get(step.tool)
            parsed = spec.parse(arguments)
        except (RegistryError, ArgumentsRejected):
            spec, parsed = None, None  # Validation says what is wrong; nothing to mend here.
        if spec is not None and parsed is not None:
            if mending := _namespaced(parsed, known_series):
                rewritten = _rewritten(arguments, mending)
                assert isinstance(rewritten, dict)  # a mapping in is a mapping out
                arguments = rewritten
                notes.extend(
                    f"step {step_id!r}: read {wrong!r} as {right!r}"
                    for wrong, right in sorted(mending.items())
                )
            if spec.discovery_only and depends:
                notes.append(f"step {step_id!r}: a catalogue search waits for no other step")
                depends = []
            table = spec.table_input(parsed) if spec.table_input is not None else None
            named = (table.source, table.input_step, *table.others) if table is not None else ()
            required = spec.required_steps(parsed) if spec.required_steps is not None else ()
            for read in (*named, *required):
                if read is not None and read in present and read != step_id and read not in depends:
                    depends.append(read)
                    notes.append(f"step {step_id!r}: reads {read!r}, added to depends_on")
        steps.append(
            step.model_copy(
                update={"step_id": step_id, "arguments": arguments, "depends_on": depends}
            )
        )
    if not notes:
        return plan, ()
    return plan.model_copy(update={"steps": steps}), tuple(notes)
