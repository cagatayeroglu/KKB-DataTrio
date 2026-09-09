"""M12-01/02/03 regressions for the medallion store.

Cases are shaped like the two real sources documented in BDDK_SOURCE and
EVDS_SOURCE: a monthly stock in million TRY, and a weekly Friday-anchored rate.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime

import pytest

from kkb_agent.core import (
    Aggregation,
    CumulativeKind,
    Frequency,
    Scale,
    SourceRef,
    StockFlow,
    WeeklyAnchor,
)
from kkb_agent.lakehouse import (
    LakehouseError,
    Observation,
    PeriodMismatch,
    SemanticsError,
    SeriesSemantics,
    UnresolvedSemantics,
    open_lakehouse,
    period_bounds,
)

NOW = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)
SOURCE = SourceRef(
    source_id="bddk:aylik:4",
    source_type="http-json",
    locator="opaque:bddk-aylik-tablo-4",
    retrieved_at=NOW,
)

# BDDK Aylık Bülten table 4: outstanding balance, million TRY, no accumulation.
BDDK_KONUT = SeriesSemantics(
    unit="TRY",
    scale=Scale.MILLION,
    frequency=Frequency.MONTHLY,
    observation=StockFlow.STOCK,
    cumulative=CumulativeKind.NONE,
    aggregation=Aggregation.LAST,
)
# EVDS TP.KTF12: flow rate on new housing loans, weekly, anchored to Friday.
EVDS_RATE = SeriesSemantics(
    unit="percent",
    scale=Scale.ONE,
    frequency=Frequency.WEEKLY,
    anchor=WeeklyAnchor.FRIDAY,
    observation=StockFlow.RATE,
    cumulative=CumulativeKind.NONE,
    aggregation=Aggregation.AVERAGE,
)


@pytest.fixture
def house(tmp_path):
    with open_lakehouse(tmp_path / "lake") as lake:
        yield lake


def seed(lake, payload=b'{"ok":true}'):
    return lake.record_artifact(
        payload, source=SOURCE, media_type="application/json", recorded_at=NOW
    )


class TestBronzeIsImmutable:
    def test_artifact_id_is_the_content_hash(self, house):
        payload = b'{"caption":"T\xc3\xbcketici Kredileri (milyon TL)"}'
        artifact = seed(house, payload)
        assert artifact.artifact_id == hashlib.sha256(payload).hexdigest()
        assert artifact.byte_count == len(payload)

    def test_payload_survives_byte_for_byte(self, house):
        payload = bytes(range(256)) + "Örnek çığ".encode()
        artifact = seed(house, payload)
        assert house.read_artifact(artifact.artifact_id) == payload

    def test_recording_the_same_bytes_twice_is_a_no_op(self, house):
        first = seed(house, b"same")
        second = seed(house, b"same")
        assert (second.artifact_id, second.already_present) == (first.artifact_id, True)
        assert house.connection.execute("SELECT count(*) FROM bronze_artifacts").fetchone()[0] == 1

    def test_retrieval_metadata_is_preserved(self, house):
        artifact = seed(house)
        row = house.connection.execute(
            "SELECT source_id, locator, retrieved_at, media_type"
            " FROM bronze_artifacts WHERE artifact_id = ?",
            [artifact.artifact_id],
        ).fetchone()
        assert row[0] == SOURCE.source_id
        assert row[1] == SOURCE.locator
        assert row[2] == NOW
        assert row[3] == "application/json"

    def test_tampering_with_a_stored_payload_is_detected(self, house):
        artifact = seed(house, b"original bytes")
        artifact.payload_path.write_bytes(b"tampered bytes")
        with pytest.raises(LakehouseError, match="no longer matches its hash"):
            house.read_artifact(artifact.artifact_id)

    def test_naive_timestamps_are_refused(self, house):
        with pytest.raises(LakehouseError, match="timezone-aware"):
            house.record_artifact(
                b"x", source=SOURCE, media_type="application/json", recorded_at=datetime(2026, 9, 9)
            )

    def test_text_is_refused_because_bronze_stores_what_arrived(self, house):
        with pytest.raises(TypeError):
            house.record_artifact(
                "not bytes", source=SOURCE, media_type="application/json", recorded_at=NOW
            )


class TestSilverRefusesUnrecordedMeaning:
    @pytest.mark.parametrize(
        ("field", "value", "expected"),
        [
            ("scale", Scale.UNKNOWN, "scale"),
            ("frequency", Frequency.UNKNOWN, "frequency"),
            ("observation", StockFlow.UNKNOWN, "observation"),
            ("cumulative", CumulativeKind.UNKNOWN, "cumulative"),
        ],
    )
    def test_an_unknown_semantic_blocks_promotion(self, house, field, value, expected):
        artifact = seed(house)
        broken = SeriesSemantics(
            **{
                **{
                    "unit": "TRY",
                    "scale": Scale.MILLION,
                    "frequency": Frequency.MONTHLY,
                    "observation": StockFlow.STOCK,
                    "cumulative": CumulativeKind.NONE,
                },
                field: value,
            }
        )
        assert expected in broken.unresolved
        with pytest.raises(UnresolvedSemantics) as excinfo:
            house.register_series(
                "s", title="t", semantics=broken, artifact_id=artifact.artifact_id
            )
        assert expected in excinfo.value.missing

    def test_a_resolved_series_reports_nothing_unresolved(self):
        assert BDDK_KONUT.unresolved == ()
        assert EVDS_RATE.unresolved == ()

    def test_a_weekly_series_must_name_its_anchor(self):
        with pytest.raises(SemanticsError, match="weekday its period ends on"):
            SeriesSemantics(
                unit="percent",
                scale=Scale.ONE,
                frequency=Frequency.WEEKLY,
                observation=StockFlow.RATE,
                cumulative=CumulativeKind.NONE,
            )

    def test_a_rate_cannot_declare_summing(self):
        with pytest.raises(SemanticsError, match="cannot be summed"):
            SeriesSemantics(
                unit="percent",
                scale=Scale.ONE,
                frequency=Frequency.MONTHLY,
                observation=StockFlow.RATE,
                cumulative=CumulativeKind.NONE,
                aggregation=Aggregation.SUM,
            )

    def test_only_a_flow_can_accumulate(self):
        with pytest.raises(SemanticsError, match="Only a flow series can accumulate"):
            SeriesSemantics(
                unit="TRY",
                scale=Scale.MILLION,
                frequency=Frequency.MONTHLY,
                observation=StockFlow.STOCK,
                cumulative=CumulativeKind.YEARLY_RESET,
            )

    def test_an_index_must_record_its_base_year(self):
        with pytest.raises(SemanticsError, match="base year"):
            SeriesSemantics(
                unit="index",
                scale=Scale.ONE,
                frequency=Frequency.MONTHLY,
                observation=StockFlow.INDEX,
                cumulative=CumulativeKind.NONE,
            )

    def test_a_series_must_cite_a_bronze_artifact(self, house):
        with pytest.raises(LakehouseError, match="must cite a bronze artifact"):
            house.register_series("s", title="t", semantics=BDDK_KONUT, artifact_id="0" * 64)

    def test_semantics_cannot_be_changed_underneath_stored_rows(self, house):
        artifact = seed(house)
        house.register_series(
            "k", title="Konut", semantics=BDDK_KONUT, artifact_id=artifact.artifact_id
        )
        relabelled = SeriesSemantics(
            unit="TRY",
            scale=Scale.THOUSAND,  # the 1000x error, arriving as a re-registration
            frequency=Frequency.MONTHLY,
            observation=StockFlow.STOCK,
            cumulative=CumulativeKind.NONE,
            aggregation=Aggregation.LAST,
        )
        with pytest.raises(LakehouseError, match="different semantics"):
            house.register_series(
                "k", title="Konut", semantics=relabelled, artifact_id=artifact.artifact_id
            )

    def test_semantics_round_trip_through_storage(self, house):
        artifact = seed(house)
        house.register_series(
            "r", title="Oran", semantics=EVDS_RATE, artifact_id=artifact.artifact_id
        )
        assert house.semantics_of("r") == EVDS_RATE


class TestPeriodsMatchTheDeclaredCalendar:
    def test_monthly_bounds_cover_the_whole_month(self):
        assert period_bounds(Frequency.MONTHLY, date(2026, 6, 30)) == (
            date(2026, 6, 1),
            date(2026, 6, 30),
        )
        assert period_bounds(Frequency.MONTHLY, date(2024, 2, 29)) == (
            date(2024, 2, 1),
            date(2024, 2, 29),
        )

    def test_quarterly_bounds_cover_three_months(self):
        assert period_bounds(Frequency.QUARTERLY, date(2026, 6, 30)) == (
            date(2026, 4, 1),
            date(2026, 6, 30),
        )

    def test_a_quarter_cannot_end_in_a_non_quarter_month(self):
        with pytest.raises(PeriodMismatch, match="cannot end in month 5"):
            period_bounds(Frequency.QUARTERLY, date(2026, 5, 31))

    def test_a_month_must_end_on_its_last_day(self):
        with pytest.raises(PeriodMismatch, match="last day of a month"):
            period_bounds(Frequency.MONTHLY, date(2026, 6, 29))

    def test_a_weekly_period_ends_on_its_anchor_and_spans_seven_days(self):
        # 2026-08-28 is the Friday BDDK's weekly bulletin labels week 35.
        assert period_bounds(Frequency.WEEKLY, date(2026, 8, 28), anchor=WeeklyAnchor.FRIDAY) == (
            date(2026, 8, 22),
            date(2026, 8, 28),
        )

    def test_a_friday_series_rejects_a_thursday_observation(self, house):
        artifact = seed(house)
        house.register_series(
            "r", title="Oran", semantics=EVDS_RATE, artifact_id=artifact.artifact_id
        )
        with pytest.raises(PeriodMismatch, match="not a friday"):
            house.append_observations(
                "r", [Observation(date(2026, 8, 21), date(2026, 8, 27), 41.2)]
            )

    def test_the_two_weekly_anchors_do_not_accept_each_others_dates(self):
        friday = date(2026, 8, 28)
        assert period_bounds(Frequency.WEEKLY, friday, anchor=WeeklyAnchor.FRIDAY)
        with pytest.raises(PeriodMismatch, match="not a wednesday"):
            period_bounds(Frequency.WEEKLY, friday, anchor=WeeklyAnchor.WEDNESDAY)

    def test_a_week_may_cross_a_month_boundary(self, house):
        artifact = seed(house)
        house.register_series(
            "r", title="Oran", semantics=EVDS_RATE, artifact_id=artifact.artifact_id
        )
        # 2026-07-03 is a Friday; its week starts in June.
        assert (
            house.append_observations("r", [Observation(date(2026, 6, 27), date(2026, 7, 3), 40.5)])
            == 1
        )


class TestObservationsKeepTheirValues:
    def test_the_real_monthly_series_loads_and_reads_back(self, house):
        artifact = seed(house)
        house.register_series(
            "bddk:konut",
            title="Tüketici Kredileri - Konut",
            semantics=BDDK_KONUT,
            artifact_id=artifact.artifact_id,
        )
        # Published values for 2026/4 through 2026/6, million TRY.
        published = {
            date(2026, 4, 30): 767314.0,
            date(2026, 5, 31): 782918.0,
            date(2026, 6, 30): 801438.0,
        }
        written = house.append_observations(
            "bddk:konut",
            [
                Observation(date(end.year, end.month, 1), end, value)
                for end, value in published.items()
            ],
        )
        assert written == 3
        rows = house.connection.execute(
            "SELECT period_end, value FROM silver_observations"
            " WHERE series_id = ? ORDER BY period_end",
            ["bddk:konut"],
        ).fetchall()
        assert dict(rows) == published

    def test_a_missing_observation_stays_null(self, house):
        artifact = seed(house)
        house.register_series(
            "k", title="K", semantics=BDDK_KONUT, artifact_id=artifact.artifact_id
        )
        house.append_observations(
            "k",
            [
                Observation(date(2026, 5, 1), date(2026, 5, 31), None),
                Observation(date(2026, 6, 1), date(2026, 6, 30), 801438.0),
            ],
        )
        missing, total = house.connection.execute(
            "SELECT count(*) - count(value), sum(value)"
            " FROM silver_observations WHERE series_id = 'k'"
        ).fetchone()
        assert missing == 1
        assert total == pytest.approx(801438.0)

    def test_a_rejected_batch_writes_nothing(self, house):
        artifact = seed(house)
        house.register_series(
            "k", title="K", semantics=BDDK_KONUT, artifact_id=artifact.artifact_id
        )
        with pytest.raises(PeriodMismatch):
            house.append_observations(
                "k",
                [
                    Observation(date(2026, 5, 1), date(2026, 5, 31), 782918.0),
                    Observation(date(2026, 6, 1), date(2026, 6, 15), 801438.0),
                ],
            )
        assert (
            house.connection.execute("SELECT count(*) FROM silver_observations").fetchone()[0] == 0
        )

    def test_two_values_for_one_period_are_refused(self, house):
        artifact = seed(house)
        house.register_series(
            "k", title="K", semantics=BDDK_KONUT, artifact_id=artifact.artifact_id
        )
        with pytest.raises(LakehouseError, match="two observations"):
            house.append_observations(
                "k",
                [
                    Observation(date(2026, 6, 1), date(2026, 6, 30), 801438.0),
                    Observation(date(2026, 6, 1), date(2026, 6, 30), 801439.0),
                ],
            )

    def test_observations_need_a_registered_series(self, house):
        with pytest.raises(LakehouseError, match="No silver series"):
            house.append_observations(
                "nope", [Observation(date(2026, 6, 1), date(2026, 6, 30), 1.0)]
            )


class TestStoreLayout:
    def test_layers_and_database_are_created(self, tmp_path):
        root = tmp_path / "lake"
        with open_lakehouse(root) as lake:
            assert lake.bronze.is_dir() and lake.silver.is_dir() and lake.gold.is_dir()
        assert (root / "kkb.duckdb").exists()

    def test_reopening_preserves_everything(self, tmp_path):
        root = tmp_path / "lake"
        with open_lakehouse(root) as lake:
            artifact = seed(lake, b"persisted")
            lake.register_series(
                "k", title="K", semantics=BDDK_KONUT, artifact_id=artifact.artifact_id
            )
            lake.append_observations(
                "k", [Observation(date(2026, 6, 1), date(2026, 6, 30), 801438.0)]
            )
        with open_lakehouse(root) as lake:
            assert lake.read_artifact(artifact.artifact_id) == b"persisted"
            assert lake.semantics_of("k") == BDDK_KONUT
            assert lake.connection.execute(
                "SELECT value FROM silver_observations WHERE series_id = 'k'"
            ).fetchone()[0] == pytest.approx(801438.0)

    def test_silver_exports_to_parquet_and_reads_back(self, house):
        artifact = seed(house)
        house.register_series(
            "k", title="K", semantics=BDDK_KONUT, artifact_id=artifact.artifact_id
        )
        house.append_observations("k", [Observation(date(2026, 6, 1), date(2026, 6, 30), 801438.0)])
        written = house.export_silver()
        assert {path.name for path in written} == {
            "silver_series.parquet",
            "silver_observations.parquet",
        }
        observations = house.silver / "silver_observations.parquet"
        value = house.connection.execute(
            f"SELECT value FROM read_parquet('{observations}')"
        ).fetchone()[0]
        assert value == pytest.approx(801438.0)

    def test_a_file_cannot_be_used_as_a_root(self, tmp_path):
        occupied = tmp_path / "not-a-dir"
        occupied.write_text("x")
        with pytest.raises(LakehouseError, match="not a directory"):
            with open_lakehouse(occupied):
                pass
