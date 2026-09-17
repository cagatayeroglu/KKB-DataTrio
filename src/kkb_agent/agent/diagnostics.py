"""Content-free plan attempt diagnostics (DEC-135, M11).

Records phase, attempt index, outcome, and rejection category only.
Never logs message strings, prompts, plans, fingerprints, answers, or values.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from kkb_agent.agent.executor import RejectionCategory


@dataclass(frozen=True, slots=True)
class PlanAttempt:
    phase: Literal["initial", "continuation"]
    attempt: int  # 1-based, bounded by max_plan_repairs + 1
    outcome: Literal["accepted", "rejected", "repeated_plan", "provider_schema_error"]
    category: RejectionCategory | None = None  # only for rejected / repeated_plan
