"""Which argument fields carry catalog series identities, declared by the contract.

The discovery admission rule needs to know, for a proposed plan, exactly which
catalog series it would read. Reading that off field *names* would be a hidden
list that silently goes stale whenever a tool gains an argument. Instead each
tool's argument model says so in its own type:

- `SeriesId` marks a field whose value is a catalog series identity.
- `OpaqueSeriesReference` marks a field that may name series in a form this
  module cannot enumerate, such as SQL text.

A model carrying an opaque field can never be proven exhaustively, so callers
treat it as "identities unknown" rather than "no identities". Adding an argument
without a marker is therefore safe by default: it contributes no identity, and
an unmarked *opaque* field would only ever make the rule stricter, never looser.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import UnionType
from typing import Annotated, Union, get_args, get_origin, get_type_hints

from pydantic import BaseModel


@dataclass(frozen=True, slots=True)
class SeriesIdentity:
    """Marker: this field's value is a catalog series identity."""


@dataclass(frozen=True, slots=True)
class OpaqueSeriesReference:
    """Marker: this field may name series identities that cannot be enumerated."""


#: A catalog series identity argument. Use beside the field's own constraints.
SeriesId = Annotated[str, SeriesIdentity()]


def _markers(annotation: object, _depth: int = 0) -> tuple[object, ...]:
    """Markers on the annotation, on a member of its union, or on the element of its list.

    `SeriesId | None` and `list[SeriesId]` carry the marker one level down. Reading only
    the outer annotation left an optional identity (a co-movement driver) uncounted, so a
    plan naming an unproven driver beside a proven series could skip discovery.
    """
    if _depth > 4:  # pragma: no cover - argument annotations do not nest this deep
        return ()
    if get_origin(annotation) is Annotated:
        inner, *markers = get_args(annotation)
        return (*markers, *_markers(inner, _depth + 1))
    if get_origin(annotation) in (Union, UnionType, list, tuple):
        return tuple(m for arg in get_args(annotation) for m in _markers(arg, _depth + 1))
    return ()


#: Argument models nest at most a few levels; the guard is against a cycle, not a shape.
_MAX_DEPTH = 8


def declared_series_identities(arguments: BaseModel, _depth: int = 0) -> frozenset[str] | None:
    """The catalog identities these arguments name, or None when one may be hidden.

    None means the arguments can reach a series this function cannot see, so the
    caller must not conclude the plan names no series.

    A tool whose operations differ by shape wraps them in a discriminated union, so
    the marked field sits on the selected member rather than on the model the plan
    carries. Nested models are therefore searched too: an identity counts wherever
    it is declared, and one opaque field anywhere makes the whole answer unknown.
    """
    if _depth > _MAX_DEPTH:  # pragma: no cover - argument models do not nest this deep
        return None
    try:
        hints = get_type_hints(type(arguments), include_extras=True)
    except Exception:  # pragma: no cover - a model whose annotations cannot resolve
        return None
    found: set[str] = set()
    for name in type(arguments).model_fields:
        markers = _markers(hints.get(name))
        if any(isinstance(marker, OpaqueSeriesReference) for marker in markers):
            return None
        value = getattr(arguments, name, None)
        if any(isinstance(marker, SeriesIdentity) for marker in markers):
            if isinstance(value, str) and value:
                found.add(value)
            elif isinstance(value, (list, tuple)):
                found.update(item for item in value if isinstance(item, str) and item)
            continue
        if isinstance(value, BaseModel):
            nested = declared_series_identities(value, _depth + 1)
            if nested is None:
                return None
            found |= nested
    return frozenset(found)
