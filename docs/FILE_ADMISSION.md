# M1-02 — File admission policy

[ingestion_policy.py](../src/kkb_agent/ingestion_policy.py) implements standalone admission/limit/storage guards for [M1-02](ROADMAP.md#m1). It uses only the Python standard library and does not select an analytical engine or depend on the stash-only SourceAdapter. [INGESTION_PROFILE](INGESTION_PROFILE.md) remains the result specification.

Admission checks establish whether input may proceed to a future bounded loader. They do not establish a valid table, known semantics, or an `ok` profile. No HTTP upload route, source adapter, CSV/XLSX loader, profiling service, or data retention backend is enabled by this change.

## Initial format policy

| Extension | Declared MIME | Content checks implemented |
| --- | --- | --- |
| `.csv` | `text/csv`; optional UTF-8 charset | Bounded bytes, UTF-8/UTF-8 BOM decoding, nonempty text, no binary control characters, reject leading markup/PDF signatures. No delimiter, header, numeric/date conversion, row dropping, or locale inference. |
| `.xlsx` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | ZIP local-header signature, readable central directory, required OOXML part names (`[Content_Types].xml`, `_rels/.rels`, `xl/workbook.xml`, at least one worksheet), bounded archive metadata. No extraction or XML/cell interpretation. |

Extension and MIME are case-normalized; missing/generic/mismatched MIME is rejected rather than guessed. CSV MIME parameters other than UTF-8 charset are rejected. `.xls`, `.xlsm`, PDF, HTML, and other formats remain unsupported. These are initial local policy choices, not claims about the organizer's hidden input set; add formats only with their own bounded path and tests.

Original filenames must be nonempty basenames of at most 255 UTF-8 bytes with no path separators, colon, control characters, or leading/trailing whitespace. They never select a storage destination. A valid unfamiliar basename is treated exactly like a familiar one. Filename/provenance retention belongs to the caller and must not leak through logs.

CSV has no authoritative magic signature: successful preflight proves admissible text, not syntactically valid CSV. M1-06/M1-13 must reject malformed/header-only tables under an explicit parsing declaration. XLSX envelope checks do not validate XML, CRCs, relationship targets, actual sheet content, or truthful expansion metadata; M1-10 must validate these while reading under enforced output/time bounds. No archive member is extracted, formula/macro executed, or link resolved here.

## Practical local limits

Both initial formats use `AdmissionLimits`; callers may supply explicitly reviewed tighter/different positive integer limits. Overrides are operator configuration, never uploaded instructions or model-generated arguments. Defaults keep development bounded without depending on platform/model answers.

| Budget | Default | Enforcement in M1-02 |
| --- | --- | --- |
| Uploaded bytes | 10 MiB | Reader requests at most 64 KiB per read and stops at the cap plus one sentinel byte; rejects oversize before staging. Short reads are supported. |
| Data rows / columns | 100,000 / 256 | `check_table_size`; caller must invoke incrementally in the future loader, not after unbounded allocation. Header is not a data row. |
| Total cells | 1,000,000 | Product limit in `check_table_size`, including all selected columns. |
| Cell / label length | 65,536 / 256 Unicode characters | `check_field`; future loader/profile integration required. No silent truncation. |
| Serialized profile | 1 MiB | `check_profile_size`; future bounded serializer must also avoid unbounded intermediate output. |
| XLSX sheets / ZIP entries | 20 / 1,024 | Counts from package entry metadata; not a substitute for workbook relationship validation. |
| XLSX expanded size | 50 MiB total | Declared ZIP sizes checked before any extraction; future loader must enforce actual expanded-byte limits too. |
| XLSX compression ratio | 100:1 per member | Declared uncompressed/compressed sizes; may conservatively reject highly repetitive workbooks. |
| Parser time | 5 seconds | Configuration only; no parser runs here. Future parser must have enforceable cancellation/resource bounds; an outer timeout alone is insufficient. |

Exact limits are inclusive; limit + 1 fails. Dimension checks accept zero while counting incrementally, but the completed loader must reject zero-row/header-only input per M1-01/M1-13. Row/cell/profile/time limits are not advertised as enforced over an uploaded file until the corresponding loader/profile calls these guards.

XLSX preflight rejects unsafe member paths, duplicate names (including case variants), encrypted or symlink members, unsupported compression, macro binary members, embedded objects, and external-link parts. Only stored/deflated ZIP members are admitted. These checks are a conservative envelope filter, not a full document security verdict.

## Transient storage and errors

`staged_upload(...)` validates metadata/content before creating anything, then creates a generated `upload-*` directory (0700) and exclusive `input.csv` or `input.xlsx` (0600) beneath an existing, operator-owned `storage_root`. Use an ignored local directory such as repository `uploads/`, separately provisioned by the operator. The API has no default path, never creates arbitrary parent directories, rejects a symlink/missing root, and must never receive a root from file metadata or model output. The root and its parents must remain under operator control during the operation.

The context manager removes staging on normal exit and downstream exceptions; callers must finish reading within the context. Failed storage operations return a sanitized code; cleanup failure is reported as `STORAGE_FAILED` for operator handling. This is temporary processing only, not permission to retain organizer/private inputs or a workspace persistence decision. Tests create synthetic inputs under pytest temporary directories; no private inputs are used.

`admit_upload(...)` accepts a blocking binary stream whose I/O timeout is already controlled by its caller. It bounds bytes, not the time a stream's `read` can block; remote retrieval still belongs behind safe-fetch. Accepted bytes remain unchanged and are omitted from the result's representation. The guard does not infer units, frequency, stock/flow, or cumulative semantics.

`AdmissionError` exposes a fixed `RejectionCode`, never a copied filename, path, cell, or low-level exception. `profile_failure(source_ref)` maps rejection into the M1-01 shape with `data_ref: null`, `row_count: null`, empty columns/semantics, and a diagnostic code. Its source reference must come from the caller's controlled provenance identity, not arbitrary source text. Admission success itself never emits an `ok` profile.

## Targeted verification and next integration

Run `PYTHONPATH=src python3.12 -m pytest -q tests/unit/test_ingestion_policy.py` and touched-file Ruff checks. Tests use small synthetic text/ZIP buffers, exact-limit/one-over cases, rejected-input instrumentation, ambiguous values preserved byte-for-byte, and temporary storage cleanup/permissions. They do not prove future loader/profile behavior.

M1-03 still requires the team's Q-TEAM-02 decision. M1-04 is the next independent candidate: add the committed synthetic CSV fixture and expected values without choosing an engine. Loader tasks later integrate these guards with validated M0 contracts and must add real byte/row/column/parser-call instrumentation under M1-14; this task does not mark those tasks complete.
