"""M5-10/11/12 regressions for the workspace artifact DAG.

The shape under test is the organizer's own three-turn scenario: build a table,
then twice more change it "without disturbing" what is already there.
"""

from __future__ import annotations

import duckdb
import pytest

from kkb_agent.agent import ArtifactKind, Workspace, WorkspaceError, artifact_id

SOURCE = ArtifactKind.SOURCE
COLUMN = ArtifactKind.COLUMN
TABLE = ArtifactKind.TABLE


@pytest.fixture
def workspace():
    with duckdb.connect() as connection:
        yield Workspace.open(connection)


def turn_one(space):
    """Housing credit and its rate, on one table."""
    space.define("range", SOURCE, parameters={"from": "2021-01", "to": "2025-12"})
    space.define("konut_stok", COLUMN, parameters={"series": "bddk:konut"}, inputs=["range"])
    space.define("konut_faiz", COLUMN, parameters={"series": "evds:TP.KTF12"}, inputs=["range"])
    return space.define("tablo", TABLE, inputs=["konut_stok", "konut_faiz"])


class TestTurnOneBuildsTheTable:
    def test_names_are_bound(self, workspace):
        turn_one(workspace)
        assert workspace.names() == ["konut_faiz", "konut_stok", "range", "tablo"]
        assert workspace.stale() == set()

    def test_an_identical_definition_is_a_no_op(self, workspace):
        turn_one(workspace)
        before = workspace.resolve("konut_stok")
        again = workspace.define(
            "konut_stok", COLUMN, parameters={"series": "bddk:konut"}, inputs=["range"]
        )
        assert again.artifact_id == before.artifact_id
        assert workspace.history("konut_stok") == [before]

    def test_the_id_is_the_definition_not_the_underlying_data(self):
        first = artifact_id(COLUMN, "c", {"series": "a"}, ["x"])
        assert first == artifact_id(COLUMN, "c", {"series": "a"}, ["x"])
        assert first != artifact_id(COLUMN, "c", {"series": "b"}, ["x"])
        assert first != artifact_id(COLUMN, "c", {"series": "a"}, ["y"])

    def test_a_recorded_value_participates_in_the_id(self):
        # Without this, recording a new result under an unchanged definition
        # would be treated as a no-op: the old number stays bound and no
        # dependent is marked stale.
        definition = artifact_id(COLUMN, "c", {"series": "a"}, ["x"])
        with_value = artifact_id(COLUMN, "c", {"series": "a"}, ["x"], "digest-1")

        assert with_value != definition
        assert with_value != artifact_id(COLUMN, "c", {"series": "a"}, ["x"], "digest-2")

    def test_a_definition_hashes_as_it_did_before_values_existed(self):
        # Adding the argument must not renumber every artifact already stored.
        assert artifact_id(COLUMN, "c", {}, []) == artifact_id(COLUMN, "c", {}, [], None)

    def test_input_order_matters(self):
        # A ratio of A to B is not the ratio of B to A.
        assert artifact_id(COLUMN, "r", {}, ["a", "b"]) != artifact_id(COLUMN, "r", {}, ["b", "a"])

    def test_an_undefined_input_is_refused(self, workspace):
        with pytest.raises(WorkspaceError, match="depends on undefined 'ghost'"):
            workspace.define("c", COLUMN, inputs=["ghost"])

    def test_self_dependency_is_refused(self, workspace):
        turn_one(workspace)
        with pytest.raises(WorkspaceError, match="cannot depend on itself"):
            workspace.define("tablo", TABLE, inputs=["tablo"])

    def test_a_cycle_is_refused(self, workspace):
        turn_one(workspace)
        with pytest.raises(WorkspaceError, match="dependency cycle"):
            workspace.define("range", SOURCE, inputs=["tablo"])


class TestTurnTwoAddsWithoutDisturbing:
    """ "Tabloyu bozmadan sadece konut kredisini enflasyondan arındır." """

    def test_a_derived_column_leaves_its_inputs_untouched(self, workspace):
        turn_one(workspace)
        before = {name: workspace.resolve(name).artifact_id for name in workspace.names()}

        workspace.define(
            "tufe", COLUMN, parameters={"series": "evds:bie_tukfiy2025"}, inputs=["range"]
        )
        workspace.define(
            "konut_reel",
            COLUMN,
            parameters={"operation": "deflate", "base": "2025-12"},
            inputs=["konut_stok", "tufe"],
        )

        # The existing columns are the same artifacts they were.
        for name in ("konut_stok", "konut_faiz", "range"):
            assert workspace.resolve(name).artifact_id == before[name]
        assert workspace.stale() == set()

    def test_the_new_column_records_what_produced_it(self, workspace):
        turn_one(workspace)
        workspace.define("tufe", COLUMN, parameters={"series": "x"}, inputs=["range"])
        derived = workspace.define(
            "konut_reel",
            COLUMN,
            parameters={"operation": "deflate", "base": "2025-12"},
            inputs=["konut_stok", "tufe"],
        )
        assert derived.parameters["operation"] == "deflate"
        assert derived.parameters["base"] == "2025-12"
        assert len(derived.inputs) == 2


class TestTurnThreeAddsAnotherColumn:
    """ "Bu tabloyu hiç bozmadan yeni bir sütun olarak konut fiyat endeksini getir." """

    def test_adding_a_column_recomputes_nothing(self, workspace):
        turn_one(workspace)
        before = {name: workspace.resolve(name).artifact_id for name in workspace.names()}

        workspace.define("kfe", COLUMN, parameters={"series": "evds:TP.KFE.TR"}, inputs=["range"])
        extended = workspace.define("tablo", TABLE, inputs=["konut_stok", "konut_faiz", "kfe"])

        for name in ("konut_stok", "konut_faiz", "range"):
            assert workspace.resolve(name).artifact_id == before[name]
        # The table itself is a new artifact, because it now holds a new column.
        assert extended.artifact_id != before["tablo"]
        assert len(workspace.history("tablo")) == 2


class TestChangingAnInputInvalidatesExactlyItsDependents:
    def test_a_changed_range_marks_everything_downstream_stale(self, workspace):
        turn_one(workspace)
        workspace.define("faiz_disi", COLUMN, parameters={"series": "unrelated"})

        workspace.define("range", SOURCE, parameters={"from": "2021-01", "to": "2026-06"})

        assert workspace.stale() == {"konut_stok", "konut_faiz", "tablo"}
        # A column that never depended on the range is untouched.
        assert not workspace.is_stale("faiz_disi")
        # The range itself is current: it is the thing that changed.
        assert not workspace.is_stale("range")

    def test_a_correction_invalidates_transitively(self, workspace):
        turn_one(workspace)
        workspace.define("tufe", COLUMN, parameters={"series": "x"}, inputs=["range"])
        workspace.define(
            "konut_reel", COLUMN, parameters={"operation": "deflate"}, inputs=["konut_stok", "tufe"]
        )
        workspace.define("range", SOURCE, parameters={"from": "2022-01", "to": "2026-06"})
        assert "konut_reel" in workspace.stale()

    def test_history_survives_the_change(self, workspace):
        turn_one(workspace)
        first = workspace.resolve("range")
        workspace.define("range", SOURCE, parameters={"from": "2021-01", "to": "2026-06"})
        history = workspace.history("range")
        assert [item.artifact_id for item in history][0] == first.artifact_id
        assert len(history) == 2
        # The superseded artifact is still readable, so "what did it say before"
        # remains answerable.
        assert workspace.artifact(first.artifact_id).parameters["to"] == "2025-12"


class TestRefreshing:
    def test_refresh_rebinds_to_the_current_inputs(self, workspace):
        turn_one(workspace)
        workspace.define("range", SOURCE, parameters={"from": "2021-01", "to": "2026-06"})
        stale_id = workspace.resolve("konut_stok", allow_stale=True).artifact_id

        refreshed = workspace.refresh("konut_stok")

        assert refreshed.artifact_id != stale_id
        assert not workspace.is_stale("konut_stok")
        assert refreshed.parameters == {"series": "bddk:konut"}

    def test_refreshing_before_its_inputs_is_refused(self, workspace):
        turn_one(workspace)
        workspace.define("range", SOURCE, parameters={"from": "2021-01", "to": "2026-06"})
        with pytest.raises(WorkspaceError, match="after its stale inputs: konut_faiz, konut_stok"):
            workspace.refresh("tablo")

    def test_the_refresh_order_puts_inputs_first(self, workspace):
        turn_one(workspace)
        workspace.define("range", SOURCE, parameters={"from": "2021-01", "to": "2026-06"})
        order = workspace.refresh_order()
        assert order.index("konut_stok") < order.index("tablo")
        assert order.index("konut_faiz") < order.index("tablo")

    def test_refreshing_in_order_clears_everything(self, workspace):
        turn_one(workspace)
        workspace.define("range", SOURCE, parameters={"from": "2021-01", "to": "2026-06"})
        for name in workspace.refresh_order():
            workspace.refresh(name)
        assert workspace.stale() == set()

    def test_refreshing_an_unknown_name_is_refused(self, workspace):
        with pytest.raises(WorkspaceError, match="No artifact named"):
            workspace.refresh("ghost")


class TestPersistenceAndIsolation:
    def test_state_survives_a_reopen_on_the_same_connection(self, workspace):
        turn_one(workspace)
        reopened = Workspace.open(workspace.connection)
        assert reopened.names() == ["konut_faiz", "konut_stok", "range", "tablo"]
        assert reopened.resolve("tablo").inputs == workspace.resolve("tablo").inputs

    def test_two_workspaces_do_not_see_each_other(self, workspace):
        turn_one(workspace)
        other = Workspace.open(workspace.connection, workspace_id="other-session")
        assert other.names() == []
        other.define("range", SOURCE, parameters={"from": "2020-01", "to": "2020-12"})
        assert workspace.resolve("range").parameters["to"] == "2025-12"

    def test_a_workspace_needs_an_id(self, workspace):
        with pytest.raises(WorkspaceError, match="needs an id"):
            Workspace(workspace.connection, "  ")

    def test_an_artifact_needs_a_name(self, workspace):
        with pytest.raises(WorkspaceError, match="needs a name"):
            workspace.define("  ", COLUMN)
