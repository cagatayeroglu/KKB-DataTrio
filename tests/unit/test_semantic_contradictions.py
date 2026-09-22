"""Reject declarations that would license materially wrong arithmetic."""

import pytest

from kkb_agent.core import Aggregation, CumulativeKind, Frequency, Scale, StockFlow
from kkb_agent.lakehouse.semantics import SemanticsError, SeriesSemantics


@pytest.mark.parametrize(
    "unit,measure,aggregation,base",
    [
        ("percent", StockFlow.STOCK, Aggregation.LAST, None),
        ("TRY", StockFlow.RATE, Aggregation.LAST, None),
        ("TRY", StockFlow.STOCK, Aggregation.SUM, None),
        ("TRY", StockFlow.INDEX, Aggregation.LAST, 2020),
    ],
)
def test_incompatible_declaration_rejected(unit, measure, aggregation, base):
    with pytest.raises(SemanticsError):
        SeriesSemantics(
            unit=unit,
            scale=Scale.ONE,
            frequency=Frequency.MONTHLY,
            observation=measure,
            cumulative=CumulativeKind.NONE,
            aggregation=aggregation,
            base_year=base,
        )
