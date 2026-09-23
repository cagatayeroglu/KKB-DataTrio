"""The catalog a turn actually searches: reviewed snapshot plus the knowledge base.

The result is a new `ReviewedSnapshot` with its own content digest, built from
the reviewed one without changing any reviewed declaration:

* an archived reviewed series keeps its record, with status ARCHIVED, so search
  leaves it out and the inspector refuses to compute on it — exactly as for a
  series the reviewers archived;
* user aliases become user concepts pointing at their series, marked as user
  supplied in their definition and conditions;
* each active user dataset becomes a series with provider USER, a source that
  says it was declared by a person, and a note that it was not reviewed.

With an empty knowledge base the reviewed snapshot is returned unchanged, same
object and same digest, so nothing downstream (dense index, inspector, proofs)
can tell the difference.

When the operator enables it, the sources' own directory (DEC-176) is applied the same
way: its entries are appended after the reviewed series, never in place of one, and a
person can archive, alias or describe them like any other entry.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Final

from kkb_agent.catalog.directory import SourceDirectory
from kkb_agent.catalog.mappings import (
    Alias,
    Concept,
    Evidence,
    ReviewedSeries,
    ReviewedSnapshot,
)
from kkb_agent.catalog.normalization import normalize_search_text
from kkb_agent.catalog.records import (
    AggregationPolicy,
    CatalogRecord,
    CatalogStatus,
    CoverageRange,
)
from kkb_agent.core import Aggregation, SourceRef
from kkb_agent.knowledge.store import PROVIDER, DatasetVersion, SeriesNote

EVIDENCE_ID: Final = "user-knowledge-base"
USER_NOTE: Final = (
    "Declared by a person in the knowledge base. Its unit, scale, frequency and "
    "stock/flow meaning are that person's statement; they were not reviewed."
)


def _aliases(texts: Sequence[str]) -> tuple[Alias, ...]:
    found: list[Alias] = []
    for text in texts:
        normalized = normalize_search_text(text)
        if normalized.strip() and normalized not in {a.normalized for a in found}:
            found.append(Alias(original=text, normalized=normalized))
    return tuple(found)


def _policy(aggregation: Aggregation) -> AggregationPolicy:
    """Only what was declared: the default is permitted, every other method stays unknown."""
    if aggregation is Aggregation.UNKNOWN:
        return AggregationPolicy()
    return AggregationPolicy.model_validate({"default": aggregation.value, aggregation.value: True})


def _dataset_series(item: DatasetVersion) -> ReviewedSeries:
    ends = [o.period_end for o in item.observations]
    return ReviewedSeries(
        record=CatalogRecord(
            series_id=item.series_id,
            provider=PROVIDER,
            source_series_id=f"{item.slug}.v{item.version}",
            title=item.title,
            description=item.description,
            source=SourceRef(
                source_id=f"knowledge:{item.slug}",
                source_type="user-declared",
                locator=f"knowledge:{item.slug}.v{item.version}",
                content_hash=f"sha256:{item.content_sha256()}",
            ),
            status=CatalogStatus.ACTIVE,
            unit=item.unit,
            scale=item.scale,
            frequency=item.frequency,
            weekly_anchor=item.anchor,
            stock_flow=item.stock_flow,
            cumulative=item.cumulative,
            aggregation=_policy(item.aggregation),
            base_year=item.base_year,
            coverage=CoverageRange(start=min(ends), end=max(ends)),
        ),
        evidence_ids=(EVIDENCE_ID,),
        title_basis="documented_title",
        note=_note(item),
    )


def _note(item: DatasetVersion) -> str:
    """The standing note, and where the numbers were read when a conversation saved them.

    A series saved from an address carried no trace of that address once it was in the
    catalogue: a later conversation could find it and never say where it came from.
    """
    if not item.provenance:
        return USER_NOTE
    said = "; ".join(f"{key}={value}" for key, value in item.provenance)
    return f"{USER_NOTE} Read from: {said}"[:1024]


def _user_concept(concept_id: str, series_id: str, aliases: Sequence[str]) -> Concept | None:
    found = _aliases(aliases)
    if not found:
        return None
    return Concept(
        concept_id=concept_id,
        definition="Search aliases a person added in the knowledge base; not reviewed.",
        aliases=found,
        candidate_series_ids=(series_id,),
        resolution="MAPPED",
        clarification_required=False,
        conditions=("User-supplied alias; the series' own declaration decides its meaning.",),
        evidence_ids=(EVIDENCE_ID,),
        exclusions=("Not a reviewed mapping.",),
    )


def effective_snapshot(
    reviewed: ReviewedSnapshot,
    datasets: Sequence[DatasetVersion],
    notes: Sequence[SeriesNote],
    directory: SourceDirectory | None = None,
) -> ReviewedSnapshot:
    """The reviewed snapshot with the knowledge base applied, or itself when there is none."""
    active = [item for item in datasets if item.status == "active"]
    known = {s.record.series_id for s in reviewed.series}
    listed = (
        [item for item in directory.series if item.record.series_id not in known]
        if directory is not None
        else []
    )
    known |= {item.record.series_id for item in listed}
    relevant = [note for note in notes if note.series_id in known]
    if (
        not listed
        and not active
        and not any(note.archived or note.aliases or note.note for note in relevant)
    ):
        return reviewed

    archived = {note.series_id for note in relevant if note.archived}
    # A person's description of a reviewed series is searched like its reviewed text: by
    # words at once, by meaning once the vectors are built again (DEC-171). It is appended
    # and labelled, never a replacement for the reviewed description.
    described = {
        note.series_id: note.note.strip()
        for note in relevant
        if note.note and note.note.strip() and not note.archived
    }

    def with_description(item: ReviewedSeries) -> ReviewedSeries:
        added = described.get(item.record.series_id)
        if added is None:
            return item
        joined = " ".join(
            part for part in (item.record.description, f"Kullanıcı açıklaması: {added}") if part
        )
        return item.model_copy(
            update={"record": item.record.model_copy(update={"description": joined})}
        )

    series = [
        item.model_copy(
            update={"record": item.record.model_copy(update={"status": CatalogStatus.ARCHIVED})}
        )
        if item.record.series_id in archived
        else with_description(item)
        for item in (*reviewed.series, *listed)
    ]
    series.extend(_dataset_series(item) for item in active)

    concepts = list(reviewed.concepts)
    for note in relevant:
        if note.aliases and not note.archived:
            concept = _user_concept(f"user-alias:{note.series_id}", note.series_id, note.aliases)
            if concept is not None:
                concepts.append(concept)
    for item in active:
        concept = _user_concept(
            f"user-dataset:{item.slug}", item.series_id, (item.title, *item.aliases)
        )
        if concept is not None:
            concepts.append(concept)

    # What the catalogue *is*, never how it got here. The note version used to be
    # part of this, so archiving an entry and restoring it produced a third digest
    # for the first content: the vectors stopped covering the catalogue and every
    # meaning-based search was off until a full rebuild (finding F4-bt-10).
    state = json.dumps(
        {
            **({"directory": directory.digest} if directory is not None and listed else {}),
            "datasets": [[i.series_id, i.content_sha256()] for i in active],
            "notes": [[n.series_id, n.archived, list(n.aliases), n.note or ""] for n in relevant],
        },
        sort_keys=True,
    ).encode()
    evidence = Evidence(
        evidence_id=EVIDENCE_ID,
        path="state/knowledge.sqlite",
        revision=hashlib.sha1(state, usedforsecurity=False).hexdigest(),
        file_sha256=hashlib.sha256(state).hexdigest(),
        section="User datasets, archive flags and aliases; not reviewed.",
    )
    body = reviewed.model_dump(mode="json", exclude={"content_sha256"})
    listed_evidence = (
        [item.model_dump(mode="json") for item in directory.evidence]
        if directory is not None and listed
        else []
    )
    body.update(
        snapshot_version=f"{reviewed.snapshot_version}+kb.{evidence.file_sha256[:12]}",
        review_note=(
            f"{reviewed.review_note} Knowledge base applied; user entries are not reviewed."
            + (" Source directory applied; listed entries are not reviewed." if listed else "")
        ),
        evidence=[*body["evidence"], *listed_evidence, evidence.model_dump(mode="json")],
        series=[item.model_dump(mode="json") for item in series],
        concepts=[item.model_dump(mode="json") for item in concepts],
    )
    # The same bytes `canonical_bytes` hashes, so the digest is the snapshot's own.
    canonical = json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return ReviewedSnapshot.model_validate(
        {**body, "content_sha256": hashlib.sha256(canonical).hexdigest()}
    )
