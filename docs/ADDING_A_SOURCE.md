# Adding a source

How another official source (after EVDS and the two BDDK bulletins) joins the product. Search, the planner,
the inspector and the answer gate are source-neutral and need no change; a source is three
parts of code plus one pinned listing ([DEC-176](DECISIONS.md), [DEC-177](DECISIONS.md)).

## What a source must provide

| Part | What it is | Where the two existing sources have it |
| --- | --- | --- |
| Pinned listing | The source's own table of contents (titles, units, frequency, codes; **no observation**), harvested by a manual script and committed with its SHA-256 | `tests/manual/harvest_evds_directory.py` → `ingest/evds_directory_listing.py`; `tests/manual/harvest_bddk_directory.py` → `ingest/bddk_monthly_directory.py` |
| Declaration | Code that turns a listed item into declared semantics (unit, scale, frequency, stock/flow/rate, aggregation, cumulative kind) from the source's own fields, and refuses what it cannot derive | `ingest/evds_directory.py::declare_series`; `ingest/bddk_monthly.py::monthly_directory_catalog` |
| Adapter | A fixed-address request builder and a strict loader that validates the whole response against the requested calendar before anything is stored | `ingest/evds_request.py` + `ingest/evds_load.py`; `ingest/bddk_monthly_request.py` + `ingest/bddk_monthly_load.py` |
| Route | The branch in `ingest/acquisition.py::TurnAcquirer.acquire` that maps a catalogue identity to the adapter, with its window policy | `_evds`, `_bddk` |

## Steps

1. **Harvest the listing.** Write `tests/manual/harvest_<source>_directory.py`; it may call
   the network, product code may not. Commit the generated module.
2. **Declare.** Map the listing's fields to `CatalogRecord` values through closed
   vocabularies. Anything outside them is listed but not readable.
3. **Enter the catalogue.** In `catalog/directory.py::_pinned` add the entries with an
   evidence id `directory:<source>`. A source with few items lists them as series (BDDK). A
   source with many lists its containers as `<PROVIDER>:group:<code>` (EVDS) and gives a
   store like `catalog/discovered.py::DiscoveredStore` that opens a container into declared
   series on demand; `catalog/expansion.py` then needs only that store.
4. **Adapter and route.** Identity → request → strict loader → `lake.register_series` with
   the declared semantics. Add the route and the window rule to `TurnAcquirer`.
5. **Tests without network.** Fakes shaped like measured live answers, as in
   `test_source_directory.py` and `test_evds_catalogue.py`: listing pinned, declarations,
   refusals before any request, a served turn.
6. **Vectors.** The catalogue digest changes, so the vector generation is built once for the
   new catalogue (knowledge page → "Yeniden vektörle", or `POST /v1/knowledge/index`).
   Generations are immutable and reopened at restart.

## What never changes

- The model supplies no code, address or window. It names an identity a search returned.
- Vectors are built from catalogue entries (titles, descriptions, labels), never from
  observations.
- A response that is not exactly what was asked (another table, unit, row, calendar) is
  refused as a whole.

## One-off content is not a source

A page or file someone gives once is read by `web_url` or as an upload, within that
conversation. To keep its numbers for every conversation, declare a column as a dataset on
the knowledge page ([DEC-157](DECISIONS.md)). An adapter is for a publisher whose data is
asked for repeatedly and keeps growing.
