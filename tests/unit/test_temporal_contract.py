from dataclasses import replace
from datetime import date

import pytest
from test_resample import DAILY_RATE
from test_table_summary import source

from kkb_agent.agent.presentation import period_table
from kkb_agent.analytics._basis import consecutive_changes
from kkb_agent.analytics.table_shape import period_change
from kkb_agent.analytics.table_summary import summarize_column
from kkb_agent.core import Frequency, Period
from kkb_agent.lakehouse import Observation


@pytest.mark.parametrize(
    "frequency,expected", [(Frequency.DAILY, [11]), (Frequency.BUSINESS_DAY, [10, 11])]
)
def test_friday_monday_is_only_consecutive_on_explicit_business_calendar(frequency, expected):
    original = source()
    template = original.values[0]
    values = [
        template.model_copy(
            update={
                "value": amount,
                "period": Period(
                    start=date(2025, 3, day), end=date(2025, 3, day), frequency=frequency
                ),
            }
        )
        for day, amount in [(7, 100), (10, 110), (11, 121), (14, 130)]
    ]
    table = original.model_copy(update={"values": values})
    result = period_change(table, column_label="credit", kind="percent", lag=1)
    assert [v.period.end.day for v in result.values] == expected
    observations = [Observation(v.period.start, v.period.end, v.value) for v in values]
    changes, _, _ = consecutive_changes(observations, replace(DAILY_RATE, frequency=frequency))
    assert [o.period_end.day for o, _, _ in changes] == expected


def test_absent_month_counts_as_missing_and_is_visible_in_table():
    original = source()
    table = original.model_copy(update={"values": [original.values[0], original.values[2]]})
    summary = summarize_column(table, column_label="credit", aggregation="mean")
    assert summary.samples.used == 2 and summary.samples.missing == 1
    assert summary.values[0].value == 15
    assert summary.transformation.parameters["missing_periods"] == ["2025-02-28"]
    rendered = period_table(table)
    assert len(rendered.rows) == 3 and rendered.rows[1][1] == ("",)
