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


def _tables(published: dict[str, AnalyticalResult]) -> str:
    """What is already published, by name, without its values."""
    lines = [
        "Bu sohbette yayımlanmış tablolar. Değerlerini görmek ya da üzerinde işlem "
        "yapmak için bir araca adıyla ver (örneğin source=\"analiz_2\"):"
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


__all__ = ["Conversation", "Exchange", "MAX_EXCHANGE_CHARS", "MAX_NAMED_COLUMNS"]
