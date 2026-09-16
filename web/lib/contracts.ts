import { z } from "zod";
const ref = z.string().regex(/^[a-f0-9]{32}$/);
const bounded = z.string().max(8192);
const label = z.string().min(1).max(240);
export const sessionSchema = z
  .object({
    api_version: z.literal(1),
    session_id: ref,
    token: z.string().regex(/^[A-Za-z0-9_-]{43}$/),
    survives_restart: z.literal(false),
  })
  .strict();
const periodSchema = z
  .object({
    start: z.iso.date(),
    end: z.iso.date(),
    frequency: z.string(),
    weekly_anchor: z.string().nullable(),
  })
  .strict();
const samplesSchema = z
  .object({
    used: z.number().int().nonnegative(),
    missing: z.number().int().nonnegative(),
    excluded: z.number().int().nonnegative(),
    minimum_required: z.number().int().nonnegative().nullable(),
  })
  .strict();
export const cellSchema = z
  .object({
    cell_id: ref,
    slot: z.number().int().min(0).max(2047),
    label,
    value: z.number().finite(),
    display: bounded.nullable(),
    unit: label.nullable(),
    scale: z.enum(["unknown", "one", "thousand", "million", "billion"]),
    measure: z.enum(["unknown", "stock", "flow", "rate", "index"]),
    period: periodSchema.nullable(),
    samples: samplesSchema.nullable(),
    lag: z.number().int().nullable(),
  })
  .strict();
const digest = z.string().regex(/^[a-f0-9]{64}$/);
const code = z.string().regex(/^[A-Za-z0-9][A-Za-z0-9_.:;+-]{0,119}$/);
export const proofGaps = [
  "execution_not_verified",
  "input_not_recognized",
  "input_result_not_verified",
  "dataset_record_missing",
  "source_lineage_missing",
  "raw_response_limit",
  "step_limit",
  "source_limit",
  "proof_unreadable",
] as const;
const proofSourceSchema = z
  .object({
    series_id: label,
    title: label.nullable(),
    binding: z.enum(["execution_snapshot", "series_record"]),
    dataset_sha256: digest.nullable(),
    dataset_source_type: code.nullable(),
    unit: label.nullable(),
    scale: code.nullable(),
    frequency: code.nullable(),
    measure: code.nullable(),
    cumulative: code.nullable(),
    aggregation: code.nullable(),
    catalog_status: code.nullable(),
    observations: z.number().int().nonnegative().nullable(),
    missing_values: z.number().int().nonnegative().nullable(),
    first_period: z.iso.date().nullable(),
    last_period: z.iso.date().nullable(),
    parser: code.nullable(),
    normalization: label.nullable(),
    raw_responses: z.number().int().nonnegative(),
    raw_response_types: z.array(code).max(4),
    hosts: z.array(label).max(4),
    first_retrieved: z.iso.datetime({ offset: true }).nullable(),
    last_retrieved: z.iso.datetime({ offset: true }).nullable(),
  })
  .strict();
/** A fetched document one literal cell was read from; no address path or cell text. */
const proofDocumentSchema = z
  .object({
    source_type: z.literal("web_url"),
    document_format: z.enum(["csv", "xlsx", "pdf", "html"]),
    host: label.nullable(),
    content_sha256: digest,
    retrieved_at: z.iso.datetime({ offset: true }).nullable(),
    page: z.number().int().min(1).nullable(),
    table: z.number().int().min(1).nullable(),
    row: z.number().int().min(1),
    column: z.number().int().min(1),
    sheet_selected: z.boolean(),
  })
  .strict();
const proofStepSchema = z
  .object({
    producer: code,
    operation: code.nullable(),
    kind: z.string(),
    method: code.nullable(),
    execution: z.enum(["verified", "not_verified"]),
    result_version: digest,
    workspace_name: code.nullable(),
    coverage: periodSchema.nullable(),
    samples: samplesSchema.nullable(),
    inputs: z
      .array(
        z
          .object({
            kind: z.enum(["series", "result", "document"]),
            index: z.number().int().min(0).max(31),
          })
          .strict(),
      )
      .max(16),
  })
  .strict();
export const proofSchema = z
  .object({
    scope: z.literal("result"),
    availability: z.enum(["available", "partial", "unavailable"]),
    gate: z.literal("accepted"),
    steps: z.array(proofStepSchema).max(8),
    sources: z.array(proofSourceSchema).max(32),
    documents: z.array(proofDocumentSchema).max(1).default([]),
    warnings: z.array(bounded).max(16),
    limitations: z.array(bounded).max(16),
    unresolved_semantics: z.array(bounded).max(16),
    gaps: z.array(z.enum(proofGaps)).max(8),
  })
  .strict()
  .refine(
    (proof) =>
      proof.availability === "unavailable"
        ? proof.steps.length === 0 &&
          proof.sources.length === 0 &&
          proof.documents.length === 0
        : proof.steps[0]?.execution === "verified" &&
          (proof.availability === "partial" || proof.gaps.length === 0) &&
          proof.steps.every((step) =>
            step.inputs.every(
              (item) =>
                item.index <
                {
                  series: proof.sources.length,
                  result: proof.steps.length,
                  document: proof.documents.length,
                }[item.kind],
            ),
          ),
    "Proof chain is inconsistent",
  );
export const resultSchema = z
  .object({
    result_ref: ref,
    version: digest,
    kind: z.string(),
    claim_kind: z.string(),
    published: z.literal(true),
    cells: z.array(cellSchema).max(2048),
    proof: proofSchema,
  })
  .strict()
  .refine(
    (result) =>
      result.proof.steps.length === 0 ||
      result.proof.steps[0].result_version === result.version,
    "Proof must describe this exact result version",
  );
export const turnSchema = z
  .object({
    api_version: z.literal(1),
    turn_id: ref,
    request_id: ref,
    state: z.enum(["queued", "running", "completed", "failed"]),
    answer: z
      .object({
        status: z.enum(["accepted", "qualified", "abstained"]),
        text: bounded,
        omitted_claims: z.number().int().nonnegative(),
        notices: z.array(bounded).max(16),
        result: resultSchema.nullable(),
      })
      .strict()
      .nullable(),
    error: z.string().nullable(),
    events: z
      .array(
        z
          .object({
            sequence: z.number().int().min(1).max(3),
            state: z.enum(["queued", "running", "completed", "failed"]),
            elapsed_ms: z.number().int().nonnegative(),
          })
          .strict(),
      )
      .max(3),
  })
  .strict()
  .refine(
    (turn) =>
      !turn.answer?.result ||
      (turn.state === "completed" && turn.answer.status === "accepted"),
    "A published result requires an accepted completed turn",
  );

export const healthSchema = z
  .object({
    api_version: z.literal(1),
    service: z.literal("ready"),
    model_checked: z.literal(false),
    execution_mode: z.enum(["kloudeks", "scripted"]),
    max_sessions: z.number().int(),
    max_turns_per_session: z.number().int(),
    max_running_turns: z.literal(1),
    capabilities: z.array(z.string()),
  })
  .strict();
export const datasetSchema = z
  .object({
    snapshot_id: z.string(),
    catalog_version: z.string(),
    catalog_identities: z.number().int().nonnegative(),
    prepared_identities: z.number().int().nonnegative(),
    observation_rows: z.number().int().nonnegative(),
    pool_bytes: z.number().int().nonnegative(),
    files: z.number().int().nonnegative(),
    series: z.array(
      z
        .object({
          series_id: z.string(),
          title: z.string(),
          observations: z.number().int().nonnegative(),
          nonnull_observations: z.number().int().nonnegative(),
          first_period: z.iso.date().nullable(),
          last_period: z.iso.date().nullable(),
        })
        .strict(),
    ),
    live_model_checked: z.literal(false),
  })
  .strict();
export type Cell = z.infer<typeof cellSchema>;
export type Result = z.infer<typeof resultSchema>;
export type Proof = z.infer<typeof proofSchema>;
export type ProofSource = Proof["sources"][number];
export type ProofDocument = Proof["documents"][number];
export type ProofStep = Proof["steps"][number];
export type Turn = z.infer<typeof turnSchema>;
export type Session = z.infer<typeof sessionSchema>;
export type Dataset = z.infer<typeof datasetSchema>;
export type Health = z.infer<typeof healthSchema>;

export const savedSchema = z
  .object({
    session: sessionSchema,
    view_result_id: ref.optional(),
    follow_selected: z.boolean().optional(),
    turns: z
      .array(
        z
          .object({
            request_id: ref,
            question: z.string().min(1).max(4096),
            turn_id: ref.optional(),
            selected_result_id: ref.optional(),
            is_continuation: z.boolean().optional(),
            admission_error: z
              .enum([
                "invalid_result",
                "invalid_request",
                "request_conflict",
                "capacity",
              ])
              .optional(),
          })
          .strict(),
      )
      .max(24),
  })
  .strict();
export type Saved = z.infer<typeof savedSchema>;
