"""`inspect`: look at a table without putting it in the prompt.

A loop that hands every result back in full pays for a sixty-row table in every
iteration after the one that made it, and a model that can only see what it was
handed cannot check its own work. So results travel by name and this tool is how
a name becomes something readable: the columns, the coverage, the count, and a
window of rows the caller asks for.

It is the tool the demo's second question needs. "Taşıt kredisi tutarlarına faiz
oranlarını ekle" only makes sense against a table whose months and cells are
still there, and the only way to know they are is to look.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from kkb_agent.agent.executor import ExecutionContext, ToolResult, ToolStatus, analytical
from kkb_agent.agent.registry import ToolSpec
from kkb_agent.core import AnalyticalResult

#: Rows one call may return. A window, not a dump: ask again with a new offset.
MAX_ROWS = 60


class InspectArguments(BaseModel):
    """What to look at, and which part of it."""

    model_config = ConfigDict(extra="ignore")

    source: str = Field(
        min_length=1,
        max_length=64,
        description="The id of an earlier action, or the name of a published table",
    )
    columns: list[str] | None = Field(
        default=None,
        description="Only these column labels; omit for all of them",
    )
    offset: int = Field(default=0, ge=0, description="First row to return, oldest first")
    limit: int = Field(
        default=20, ge=1, le=MAX_ROWS, description=f"How many rows, at most {MAX_ROWS}"
    )


class InspectOutput(BaseModel):
    """What one look returned."""

    model_config = ConfigDict(extra="forbid")

    source: str
    kind: str
    columns: list[str]
    rows: int
    coverage: str | None = None
    offset: int
    values: list[dict[str, object]]
    #: True when more rows follow this window.
    more: bool


def _rows(result: AnalyticalResult, wanted: list[str] | None) -> list[dict[str, object]]:
    """One entry per period, with the asked-for columns beside it."""
    by_period: dict[str, dict[str, object]] = {}
    for value in result.values:
        if wanted is not None and value.label not in wanted:
            continue
        key = value.period.end.isoformat() if value.period is not None else ""
        row = by_period.setdefault(key, {"period": key})
        row[value.label] = value.value
    return [by_period[key] for key in sorted(by_period)]


def make_inspect_tool() -> ToolSpec:
    """Bind the tool. It reads what the turn already has and fetches nothing."""

    def run(arguments: BaseModel, context: ExecutionContext) -> ToolResult:
        if not isinstance(arguments, InspectArguments):  # pragma: no cover - contract
            raise TypeError("inspect received arguments it did not declare")
        found = analytical(context.outputs.get(arguments.source))
        if found is None:
            known = ", ".join(sorted(context.outputs)) or "yok"
            return ToolResult(
                ToolStatus.FAILURE,
                arguments.source,
                "inspect",
                error_category="table_reference",
                warnings=(f"{arguments.source!r} bir tablo değil. Elde olanlar: {known}",),
            )
        rows = _rows(found, arguments.columns)
        window = rows[arguments.offset : arguments.offset + arguments.limit]
        labels = list(dict.fromkeys(value.label for value in found.values))
        return ToolResult(
            ToolStatus.SUCCESS,
            arguments.source,
            "inspect",
            output=InspectOutput(
                source=arguments.source,
                kind=found.kind.value,
                columns=labels,
                rows=len(rows),
                coverage=(
                    f"{found.coverage.start}..{found.coverage.end}"
                    if found.coverage is not None
                    else None
                ),
                offset=arguments.offset,
                values=window,
                more=arguments.offset + len(window) < len(rows),
            ),
        )

    return ToolSpec(
        name="inspect",
        description=(
            "Look at a table you already have: its columns, how many periods it covers, "
            "and a window of its rows. Give source=<an action id or a published table "
            "name>, optionally columns, offset and limit. Nothing is fetched and nothing "
            "is changed; ask again with a larger offset to read further."
        ),
        arguments=InspectArguments,
        run=run,
    )


__all__ = ["InspectArguments", "InspectOutput", "MAX_ROWS", "make_inspect_tool"]
