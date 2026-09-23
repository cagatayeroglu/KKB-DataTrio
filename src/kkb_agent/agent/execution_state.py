"""Tool execution facts belong to the harness, not to narrative inference.

This is a presentation boundary, never intent detection or tool routing. Localized
names only identify operational claims to replace with recorded states; all other
interpretation stays with the writer and the existing financial evidence gate.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass

from kkb_agent.agent.executor import ExecutionOutcome
from kkb_agent.core import AnalyticalResult

# Display vocabulary, not a list of user phrases which trigger tools.
LABELS = {
    "anomaly": "Anomali",
    "causality": "Nedensellik",
    "change_detection": "Değişim tespiti",
    "lakehouse": "Lakehouse",
    "web_search": "Web araması",
    "web_url": "Web belge okuma",
    "table_transform": "Tablo dönüşümü",
    "catalog_search": "Katalog araması",
    "document_read": "Belge okuma",
    "promote_series": "Veri kaydetme",
}


@dataclass(frozen=True)
class ExecutionState:
    tool: str
    step: str | None
    execution: str
    result: str | None = None
    used: int | None = None
    minimum_required: int | None = None
    reason: str | None = None

    @property
    def incomplete(self) -> bool:
        return self.execution != "success" or self.result not in (None, "computed")

    def text(self) -> str:
        label = LABELS.get(self.tool, self.tool)
        prefix = f"{label} ({self.step or self.tool}): "
        if self.execution == "not_called":
            return prefix + "bu turda çağrılmadı."
        if self.execution == "not_run":
            return prefix + "planlandı ancak çalıştırılmadı."
        if self.execution == "failure":
            return prefix + "çalıştırıldı ancak başarısız oldu."
        state = {
            "insufficient": "veri yetersiz; güvenilir sonuç üretilemedi",
            "abstained": "araç sonuç üretmekten kaçındı",
            "undefined": "hesap tanımsız",
            "computed": "sonuç hesaplandı",
        }.get(
            self.result or "", "işlem tamamlandı" if self.execution == "success" else "kısmi sonuç"
        )
        text = prefix + "çalıştırıldı; " + state + "."
        if self.used is not None and self.incomplete:
            text += f" Kullanılan gözlem: {self.used}."
            if self.minimum_required is not None:
                text += f" Gerekli asgari gözlem: {self.minimum_required}."
        return text


def execution_states(outcome: ExecutionOutcome) -> tuple[ExecutionState, ...]:
    states = []
    for item in outcome.results:
        candidate = getattr(item.output, "result", item.output)
        result = candidate if isinstance(candidate, AnalyticalResult) else None
        states.append(
            ExecutionState(
                item.tool,
                item.step_id,
                item.status.value,
                result.status.value if result is not None else None,
                result.samples.used if result is not None and result.samples is not None else None,
                result.samples.minimum_required
                if result is not None and result.samples is not None
                else None,
                result.reason if result is not None else item.error_category,
            )
        )
    return tuple(states)


def writer_state(states: tuple[ExecutionState, ...]) -> str:
    return (
        "Recorded tool execution states (authoritative). Missing tools were not called. "
        "success means the call returned, not that analysis computed: inspect result separately. "
        "The harness presents operational status; write interpretation, not claims about whether "
        "tools ran. An insufficient result must never be described as a tool not being called.\n"
        + json.dumps([asdict(state) for state in states], ensure_ascii=False)
    )


# Finite surface guard for operational prose in the product's Turkish/English languages.
# It is deliberately separate from (and grants no exceptions to) numeric verification.
_OPERATION = re.compile(
    r"çalıştır|çalışmad|çalıştı|çağrıl|uygulan|yürütül|devreye|"
    r"\b(?:ran|run|called|executed|invoked|applied)\b",
    re.IGNORECASE,
)


def separate_status_claims(text: str) -> tuple[str, set[str]]:
    kept: list[str] = []
    mentioned: set[str] = set()
    parts = re.split(r"((?<=[.!?])\s+|\n+)", text)
    for index in range(0, len(parts), 2):
        sentence = parts[index]
        separator = parts[index + 1] if index + 1 < len(parts) else ""
        folded = sentence.casefold()
        tools = {
            name for name, label in LABELS.items() if name in folded or label.casefold() in folded
        }
        if tools and _OPERATION.search(sentence):
            mentioned.update(tools)
        else:
            kept.append(sentence + separator)
    return "".join(kept).strip() if mentioned else text, mentioned


def status_text(states: tuple[ExecutionState, ...], mentioned: set[str]) -> str:
    selected = [state for state in states if state.incomplete or state.tool in mentioned]
    missing = mentioned - {state.tool for state in states}
    selected.extend(ExecutionState(name, None, "not_called") for name in sorted(missing))
    return "\n".join(state.text() for state in selected)
