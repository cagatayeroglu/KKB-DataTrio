"""What one conversation carries from a turn into the next.

Three things travel, and they travel differently on purpose.

**What is on the table.** Every result an earlier turn published, listed by the
name it was published under, with one line saying what it is — not its cells.
The model asks for the cells by naming the table in a tool call, exactly as it
would for a series it has never seen. So "bu tabloyu bozmadan yeni bir sütun
ekle" resolves to a name that is really there, and a sixty-row table costs one
line of context instead of sixty.

**The model's own note.** At the end of a turn the loop keeps whatever the model
wrote in `state`, and hands it back at the start of the next one. This is the
only summary in the system and the model wrote it. Nothing here decides what
mattered about the last turn.

**The recent exchange.** Questions and answers as they were said, newest first
until a budget runs out. This is raw text, not a projection: what gets dropped
is the oldest, and what the model wanted to keep about it is already in its own
note. A short reference like "yalnız 2024'ü göster" needs the sentence before
it, not a description of that sentence.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass, field

from kkb_agent.core import AnalyticalResult

#: How much of the spoken conversation travels. Generous: on the served model a
#: 14k-token prompt plans in about two seconds, and the old ceiling of 700
#: characters a message clipped an analytical answer mid-table, so the planner
#: read a truncated copy of what it had itself said one turn earlier.
MAX_EXCHANGE_CHARS = 24_000

#: Beyond this a table lists its columns by count rather than by name.
MAX_NAMED_COLUMNS = 12


@dataclass(slots=True)
class Exchange:
    """One question and the answer it got, as they were said."""

    question: str
    answer: str


@dataclass(slots=True)
class Conversation:
    """The turns of one conversation, and what they left behind."""

    exchanges: list[Exchange] = field(default_factory=list)
    #: The model's own carry note, written as `state` on the turn that ended.
    note: str | None = None

    def remember(self, question: str, answer: str, note: str | None) -> None:
        """Keep this turn. The note replaces the previous one; the model owns it."""
        self.exchanges.append(Exchange(question, answer))
        if note:
            self.note = note

    def context(self, published: dict[str, AnalyticalResult]) -> dict[str, str]:
        """The blocks this conversation contributes to the next turn's prompt."""
        blocks: dict[str, str] = {}
        if published:
            blocks["tables"] = _tables(published)
        if self.note:
            blocks["note"] = (
                "Bir önceki turda kendine bıraktığın not (bunu sen yazdın):\n" + self.note
            )
        spoken = _spoken(self.exchanges)
        if spoken:
            blocks["exchange"] = spoken
        return blocks


def restored(
    messages: Iterable[tuple[str, str, str, str | None]],
    finished: Collection[str],
    note: str | None = None,
) -> Conversation:
    """A conversation rebuilt from what was stored of it, after the process lost it.

    `messages` are this conversation's own stored messages in order, each
    `(turn_id, role, text, status)`; `finished` the turns whose run completed. A turn is
    kept once, and only when it finished, its question completed and an answer was
    stored: a failed, cancelled or still-running turn was never remembered while the
    process lived, so it is not remembered now. The answer is the one the reader was
    shown, which the live memory kept before it was fitted for display. `note` is the
    model's last carry note from a finished turn, when one was recorded.

    Live 2026-09-23 a restart between A2 and A3 left the published tables in place and
    every question and answer before them gone, so the next turn started as if the
    conversation had not happened.
    """
    questions: dict[str, tuple[str, str | None]] = {}
    answers: dict[str, str] = {}
    order: list[str] = []
    for turn_id, role, text, status in messages:
        if turn_id not in order:
            order.append(turn_id)
        if role == "user":
            questions[turn_id] = (text, status)
        elif role == "assistant":
            answers[turn_id] = text
    exchanges = [
        Exchange(questions[turn_id][0], answers[turn_id])
        for turn_id in order
        if turn_id in finished
        and turn_id in questions
        and questions[turn_id][1] == "completed"
        and answers.get(turn_id, "").strip()
    ]
    return Conversation(exchanges=exchanges, note=note)


def _tables(published: dict[str, AnalyticalResult]) -> str:
    """What is already published, by name, without its values."""
    lines = [
        "Bu sohbette yayımlanmış tablolar. Değerlerini görmek ya da üzerinde işlem "
        'yapmak için bir araca adıyla ver (örneğin source="analiz_2"):'
    ]
    for name, result in published.items():
        labels = list(dict.fromkeys(value.label for value in result.values))
        columns = (
            ", ".join(labels[:MAX_NAMED_COLUMNS])
            if len(labels) <= MAX_NAMED_COLUMNS
            else f"{len(labels)} sütun"
        )
        coverage = ""
        if result.coverage is not None:
            coverage = f", {result.coverage.start}..{result.coverage.end}"
        lines.append(f"- {name}: {result.kind.value}{coverage} — {columns}")
    return "\n".join(lines)


def _spoken(exchanges: list[Exchange]) -> str:
    """The recent conversation, newest kept first, oldest dropped at the budget."""
    kept: list[str] = []
    used = 0
    for item in reversed(exchanges):
        block = f"Soru: {item.question}\nCevap: {item.answer}"
        if used + len(block) > MAX_EXCHANGE_CHARS and kept:
            break
        kept.append(block)
        used += len(block)
    if not kept:
        return ""
    return (
        "Bu sohbetin önceki turları, eskiden yeniye (veri değil, konuşma). Kısa "
        "göndermeleri ('bu tablo', 'yalnız 2024', 'en yüksek ay') bunlarla çöz:\n\n"
        + "\n\n".join(reversed(kept))
    )


__all__ = ["Conversation", "Exchange", "MAX_EXCHANGE_CHARS", "MAX_NAMED_COLUMNS", "restored"]
