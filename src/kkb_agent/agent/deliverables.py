"""Presentation selects requested artifacts; computation order is not presentation order."""

from collections.abc import Sequence
from typing import TYPE_CHECKING

from kkb_agent.core import AnalyticalResult
from kkb_agent.lakehouse.result_evidence import result_ancestors

if TYPE_CHECKING:
    from duckdb import DuckDBPyConnection


def presentation_results(
    candidates: Sequence[AnalyticalResult], connection: "DuckDBPyConnection | None"
) -> tuple[AnalyticalResult, ...]:
    """Keep independent outputs, removing only exactly preserved tables/copies.

    A changed or filtered cell cannot stand in for the original. A derived table that
    retains every original cell can, without showing the same full table twice.
    """
    unique = {result.digest(): result for result in candidates}
    retained = []
    ordered = list(unique.items())
    ancestors = (
        {
            digest: {
                version for _, version in result_ancestors(result, connection, include_steps=True)
            }
            for digest, result in ordered
        }
        if len(ordered) > 1
        else {}
    )
    for position, (digest, result) in enumerate(ordered):
        if result.values and any(
            other_digest != digest
            and digest in ancestors[other_digest]
            and (len(other.values) > len(result.values) or other_position > position)
            and all(value in other.values for value in result.values)
            and (
                not isinstance(hidden := other.parameters.get("hidden_columns"), list)
                or not any(value.label in hidden for value in result.values)
            )
            for other_position, (other_digest, other) in enumerate(ordered)
        ):
            continue
        retained.append(result)
    # The requested period table is primary; summaries/analytics remain separate artifacts.
    return tuple(
        sorted(
            retained,
            key=lambda result: len(
                {(value.period.start, value.period.end) for value in result.values if value.period}
            ),
            reverse=True,
        )
    )
