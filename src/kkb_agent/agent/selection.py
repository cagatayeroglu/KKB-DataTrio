"""Mandatory selected-table grounding, independent of financial tool names."""

from dataclasses import dataclass

import duckdb

from kkb_agent.agent.executor import PlanRejected, RejectionCategory, ValidatedPlan
from kkb_agent.agent.registry import ToolRegistry
from kkb_agent.agent.workspace import Workspace, artifact_id
from kkb_agent.core import AnalyticalResult


class SelectionError(ValueError):
    """The pinned source no longer authorizes this calculation/publication."""


@dataclass(frozen=True, slots=True)
class SelectedTable:
    workspace: Workspace
    name: str
    artifact_id: str
    version: str

    def check(self) -> AnalyticalResult:
        try:
            artifact = self.workspace.resolve(self.name)
            value = self.workspace.value_of(self.name)
            if (
                artifact.artifact_id != self.artifact_id
                or artifact.value_ref != self.version
                or value.digest() != self.version
                or artifact_id(
                    artifact.kind,
                    artifact.name,
                    artifact.parameters,
                    artifact.inputs,
                    artifact.value_ref,
                )
                != self.artifact_id
            ):
                raise SelectionError("invalid_result")
            return value
        except (ValueError, duckdb.Error):
            raise SelectionError("invalid_result") from None

    def validate_plan(self, plan: ValidatedPlan, registry: ToolRegistry) -> None:
        """Every calculation must consume the selected source or its derived step."""
        self.check()
        if all(registry.get(v.step.tool).discovery_only for v in plan.steps):
            return  # Discovery/clarification cannot publish an analytical result.
        rooted: set[str] = set()
        for validated in plan.steps:
            spec = registry.get(validated.step.tool)
            source = spec.table_input(validated.arguments) if spec.table_input else None
            if source is None or (source.source is None) == (source.input_step is None):
                raise PlanRejected(
                    "Selected-table calculations need a declared table input",
                    category=RejectionCategory.SELECTED_TABLE,
                )
            if source.source is not None and source.source != self.name:
                raise PlanRejected(
                    "Use the explicitly selected workspace source",
                    category=RejectionCategory.SELECTED_TABLE,
                )
            if source.input_step is not None and (
                source.input_step not in rooted
                or source.input_step not in validated.step.depends_on
            ):
                raise PlanRejected(
                    "Table input must derive from the selected source",
                    category=RejectionCategory.SELECTED_TABLE,
                )
            rooted.add(validated.step.step_id)
