# M13-05 — Local catalog vector index

This is the bounded offline storage/search slice selected by DEC-138. It uses
LanceDB **0.38.0**, an exact pinned runtime dependency, and the current reviewed
catalog contract (at most 40 records, 4096-dimensional vectors). It is not a
full-source catalog, live Qwen quality result or completed hybrid pipeline.

## Inputs and storage

`catalog.vectors.catalog_documents(snapshot)` builds stable ID-ordered passages
from titles, descriptions, labels, positive reviewed aliases and declared
semantics using the shared Turkish normalizer. Missing metadata stays unknown;
unresolved-only aliases/exclusion notes are not added as positive records.
A representation over 8192 UTF-8 bytes is refused instead of truncated.
No financial observation values are read or indexed.

An operator supplies a `CatalogVectors` batch with exactly one vector per
snapshot identity and the matching text digest. `VectorProfile` requires the
confirmed Qwen model/dimension, an **explicit input-policy identifier** and an
`offline_fixture` or `kloudeks` origin. The identifier is a declaration, not
proof of live approval or quality. There is no default input policy or guessed
query/passage prefix. Later embedding integration must implement/review that
policy for both kinds of input under Q-K-05.

`build_catalog_index(absolute_local_root, snapshot, vectors)` creates a fresh
local generation. Existing directories are refused. Wrong dimensions, nonfinite
or zero vectors, duplicate/missing/extra IDs and stale snapshot/text digests
fail before a directory is created. Vectors are normalized with stable scaling
and stored as Arrow float32 with a digest of those bytes. Text, identity and
concept/family IDs remain together. A manifest binds snapshot, profile, count
and row digest; it is written last. A failed build leaves no usable manifest.
Retry into a fresh directory without deleting/overwriting an earlier generation.

These directories are operator-owned artifacts, **not an upload/import format**.
Paths are never tool/model arguments. Relative paths, URI strings and UNC shares
are rejected. The local connection class is used directly, with no cloud
dispatcher, embedding-function metadata, SDK fallback or key. Hashes detect
mismatches, not an attacker controlling both database and manifest. Keep the
root out of Git, e.g. under the existing ignored `data/processed` directory.

## Opening and searching

`LocalCatalogIndex.open(root, snapshot, profile)` opens table version 1 and
requires the same snapshot, input policy and origin. It checks the fixed Arrow
schema, bounded count, representation/identity fields, vector digests and unit
norms. Missing/partial/changed content fails with fixed error categories.
Readers do not append or update the generation.

`index.search(QueryVector(...), eligible_ids=frozenset(...), limit=10)` takes
eligibility decided from reviewed metadata by the caller. The index cannot
decide archive/provider/native-frequency policy or financial meaning. Only
checked numeric ordinals enter the predicate; IDs/user strings are never SQL.
Eligibility applies **before** retrieval; empty eligibility returns immediately.
Exact cosine bypasses approximate indexes, reads all eligible bounded candidates
and sorts equal distances by ID before applying the 1–10 result limit.
Distances are not probabilities/confidence; even the nearest result is a candidate.

The separate [combined catalog layer](CATALOG_SEARCH.md#bounded-combined-candidate-contract)
maps IDs back to reviewed records for an optional operator-configured dense stage.
This index module does not combine BM25 scores, select an answer, provide financial
evidence, replan a conversation or call Kloudeks. RRF/reranking remain benchmark-gated. Broader
catalog ingestion and capacity/performance checks must precede raising the
current 40-record snapshot limit for full-source coverage.

## Validation and dependency review

`tests/unit/test_catalog_index.py` runs real LanceDB with labelled fixture
vectors: persistence/reopen, independent cosine oracle, stable ties,
prefilter-before-top-k, empty/unknown IDs, policy/origin mismatch, invalid vectors,
existing-root preservation and failed publication. This is separate from M13-09
held-out semantic quality. No model or official-source request was made.

The installed 17-package runtime dependency closure passed `pip check`.
Targeted `pip-audit` on 2026-09-14 reported one unique existing PyArrow 21.0.0
advisory twice: **CVE-2026-25087 / PYSEC-2026-113**. The raw audit exits nonzero;
it is not a clean scan. No advisory was reported for LanceDB 0.38.0 or its newly
added packages. The [Apache release announcement](https://arrow.apache.org/blog/2026/02/16/23.0.1-release/)
limits the issue to C++ IPC-file pre-buffering explicitly enabled through
`RecordBatchFileReader::PreBufferMetadata`; the [advisory reproduced by GitHub](https://github.com/advisories/GHSA-rgxp-2hwp-jwgg)
states that this is not exposed in Python bindings. This implementation uses
Python Arrow table construction and Lance's local vector table, accepts no IPC
upload and enables no such C++ API. On that evidence the report is not applicable
to this Python path. The existing PyArrow range is unchanged; no audit suppression
or gate weakening was added. A future C++/IPC integration needs reassessment;
release-wide dependency upgrade/audit policy is a separate checkpoint.

API behavior was checked against the installed pinned package and official
[LanceDB vector search documentation](https://docs.lancedb.com/search/vector-search).
Real embedding-policy confirmation, live index construction, hybrid-quality
evaluation and bounded planner consumption remain next integration steps.
