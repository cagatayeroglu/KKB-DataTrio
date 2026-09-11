"""M8-20: display text, never a replacement for a trusted ResultValue.

Six significant digits leave margin inside the existing 5e-4 relative gate.
Integer-valued floats retain every integer digit. Fixed notation is bounded
by the finite float range and avoids exponents the answer parser cannot read.
"""

from __future__ import annotations

import math
from decimal import Decimal

from kkb_agent.agent.claim_qualifiers import UNITS
from kkb_agent.core import DIMENSIONLESS, ResultValue, Scale

_SCALES = {Scale.ONE: "", Scale.THOUSAND: "bin", Scale.MILLION: "milyon", Scale.BILLION: "milyar"}
_UNITS = {
    **{unit: unit.upper() for unit in UNITS.values() if len(unit) == 3},
    "try": "TL",
    "percent": "yüzde",
    "percentage_points": "yüzde puan",
    "basis_points": "baz puan",
    "index_points": "endeks puan",
    DIMENSIONLESS: DIMENSIONLESS,
}


def format_number(value: float) -> str:
    """Return one deterministic Turkish number, readable by the existing gate.

    A lone separator followed by three digits means grouping to parse_written.
    Thus 1.234 is displayed as 1,2340, not the thousandfold-ambiguous 1,234.
    The extra zero is intentional; the verifier's locale policy is unchanged.
    """
    if not math.isfinite(value):
        raise ValueError("Only finite analytical values have display numbers")
    if value == 0:
        return "0"
    fixed = (
        format(value, ".0f") if value.is_integer() else format(Decimal(format(value, ".6g")), "f")
    )
    integer, _, fraction = fixed.partition(".")
    fraction = fraction.rstrip("0")
    sign = "-" if integer.startswith("-") else ""
    digits = integer.lstrip("-")
    groups = [digits[max(0, end - 3) : end] for end in range(len(digits), 0, -3)]
    grouped = ".".join(reversed(groups))
    if len(fraction) == 3 and "." not in grouped:
        fraction += "0"
    return sign + grouped + ("," + fraction if fraction else "")


def display_value(value: ResultValue) -> str | None:
    """Quote only supported, resolved metadata; never infer a unit or rescale.

    The vocabulary is the gate's existing currency/rate vocabulary plus its
    explicit dimensionless unit. Unsupported free-text units remain canonical
    metadata, but receive no numerical display rather than a guessed label.
    """
    if value.semantics_are_unresolved:
        return None
    folded = (value.unit or "").lower().replace("\u0307", "").replace("ı", "i")
    unit = _UNITS.get(UNITS.get(folded, folded))
    scale = _SCALES.get(value.scale)
    if unit is None or scale is None:
        return None
    number = format_number(value.value)
    return " ".join(part for part in (number, scale, unit) if part)
