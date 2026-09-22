import { z } from "zod";
const ref = z.string().regex(/^[a-f0-9]{32}$/);
const bounded = z.string().max(8192);
const label = z.string().min(1).max(240);
export const sessionSchema = z
  .object({
    api_version: z.literal(1),
    session_id: ref,
    token: z.string().regex(/^[A-Za-z0-9_-]{43}$/),
    survives_restart: z.boolean(),
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
/** A fetched document a literal cell or an added column was read from; no path or cell text. */
const proofDocumentSchema = z
  .object({
    source_type: z.enum(["web_url", "upload"]),
    document_format: z.enum(["csv", "xlsx", "pdf", "html"]),
    host: label.nullable(),
    content_sha256: digest,
    retrieved_at: z.iso.datetime({ offset: true }).nullable(),
    page: z.number().int().min(1).nullable(),
    table: z.number().int().min(1).nullable(),
    row: z.number().int().min(1).nullable(),
    column: z.number().int().min(1).nullable(),
    sheet_selected: z.boolean(),
    values_read: z.number().int().nonnegative().nullable().default(null),
    extraction: z.enum(["text", "ocr"]).default("text"),
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
    documents: z.array(proofDocumentSchema).max(4).default([]),
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
const resultContentSchema = z
  .object({
    result_ref: ref,
    version: digest,
    kind: z.string(),
    claim_kind: z.string(),
    published: z.literal(true),
    cells: z.array(cellSchema).max(2048),
    // Absent from a server older than the option; then nothing is hidden.
    hidden_columns: z.array(z.string().max(240)).max(32).default([]),
    // What each series in this result is called. A server that does not send it leaves
    // the identities as they are, which is what every server did until 2026-09-21.
    series_names: z
      .record(z.string().max(240), z.string().max(240))
      .default({}),
    proof: proofSchema,
  })
  .strict()
  .refine(
    (result) =>
      result.proof.steps.length === 0 ||
      result.proof.steps[0].result_version === result.version,
    "Proof must describe this exact result version",
  );
export const resultSchema = resultContentSchema.safeExtend({
  related: z.array(resultContentSchema).max(11).default([]),
});
const seriesChoiceSchema = z
  .object({
    series_id: z.string().min(1).max(200),
    title: z.string().min(1).max(400),
    detail: z.string().max(400),
  })
  .strict();

export const turnSchema = z
  .object({
    api_version: z.literal(1),
    turn_id: ref,
    request_id: ref,
    state: z.enum(["queued", "running", "completed", "failed"]),
    answer: z
      .object({
        status: z.enum(["accepted", "qualified", "abstained"]),
        needs_clarification: z.boolean().optional(),
        text: bounded,
        omitted_claims: z.number().int().nonnegative(),
        notices: z.array(bounded).max(16),
        result: resultSchema.nullable(),
        // Which catalogue entries the turn used without a reviewed match, and what else
        // the same search showed (DEC-177). Absent on turns stored before it existed.
        selection: z
          .object({
            chosen: z.array(seriesChoiceSchema).max(12),
            others: z.array(seriesChoiceSchema).max(10),
          })
          .strict()
          .nullable()
          .optional(),
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
      (turn.state === "completed" && turn.answer.status !== "abstained"),
    "A published result requires a completed turn that did not abstain",
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
    /** The planner model this deployment routes to; older servers omit it. */
    model: z.string().max(200).nullable().optional(),
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

export const documentAdmittedSchema = z
  .object({
    api_version: z.literal(1),
    document_ref: ref,
    document_format: z.enum(["csv", "xlsx", "pdf", "html"]),
    bytes: z
      .number()
      .int()
      .min(1)
      .max(10 * 1024 * 1024),
    sha256: digest,
  })
  .strict();
export type DocumentAdmitted = z.infer<typeof documentAdmittedSchema>;

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
            document_ref: ref.optional(),
            document_format: z.enum(["csv", "xlsx", "pdf", "html"]).optional(),
            admission_error: z
              .enum([
                "invalid_result",
                "invalid_request",
                "request_conflict",
                "capacity",
                "invalid_document",
                "not_found",
                "turn_interrupted",
                "turn_not_sent",
              ])
              .optional(),
          })
          .strict(),
      )
      // This tab's own record, not the server's policy: the per-conversation cap
      // is the server's (`max_turns_per_session`, 100 here) and a fixed 24 here
      // made a long chat unreadable after a reload.
      .max(500),
  })
  .strict();
export type Saved = z.infer<typeof savedSchema>;

const key = z.string().regex(/^[A-Za-z0-9_-]{43}$/);
export const ownerSchema = z
  .object({ api_version: z.literal(1), owner_token: key })
  .strict();
export const conversationSummarySchema = z
  .object({
    conversation_id: ref,
    title: label,
    archived: z.boolean(),
    created_at: z.iso.datetime({ offset: true }),
    updated_at: z.iso.datetime({ offset: true }),
    turns: z.number().int().nonnegative(),
  })
  .strict();
export const conversationListSchema = z
  .object({
    api_version: z.literal(1),
    conversations: z.array(conversationSummarySchema).max(200),
  })
  .strict();
export const traceConversationSummarySchema = conversationSummarySchema
  .extend({ deleted: z.boolean() })
  .strict();
export const traceConversationListSchema = z
  .object({
    api_version: z.literal(1),
    conversations: z.array(traceConversationSummarySchema).max(200),
  })
  .strict();
export const conversationDeletedSchema = z
  .object({ api_version: z.literal(1), deleted: z.literal(true) })
  .strict();
export const runsDeletedSchema = z
  .object({
    api_version: z.literal(1),
    deleted_runs: z.number().int().nonnegative(),
  })
  .strict();
export const storedMessageSchema = z
  .object({
    sequence: z.number().int().min(1),
    turn_id: ref,
    role: z.enum(["user", "assistant"]),
    text: bounded,
    status: z
      .enum([
        "accepted",
        "qualified",
        "abstained",
        "queued",
        "running",
        "completed",
        "failed",
      ])
      .nullable(),
    result_ref: ref.nullable(),
    result_version: digest.nullable(),
    document_ref: ref.nullable(),
    created_at: z.iso.datetime({ offset: true }),
  })
  .strict();
export const conversationDetailSchema = z
  .object({
    api_version: z.literal(1),
    conversation: conversationSummarySchema,
    token: key.nullable(),
    messages: z.array(storedMessageSchema).max(512),
    documents: z
      .array(
        z
          .object({
            document_ref: ref,
            name: z.string().regex(/^belge_[0-9]{1,2}$/),
            document_format: z.enum(["csv", "xlsx", "pdf", "html"]),
            bytes: z.number().int().positive(),
            sha256: digest,
            admitted_at: z.iso.datetime({ offset: true }),
          })
          .strict(),
      )
      .max(4),
    // Titles the pending clarification offered, so a reopened chat can show them.
    pending_offered: z.array(z.string().min(1).max(240)).max(12).default([]),
  })
  .strict();
export type ConversationSummary = z.infer<typeof conversationSummarySchema>;
export type TraceConversationSummary = z.infer<
  typeof traceConversationSummarySchema
>;
export type ConversationDetail = z.infer<typeof conversationDetailSchema>;
export type StoredMessage = z.infer<typeof storedMessageSchema>;

export const runProgressSchema = z
  .object({
    api_version: z.literal(1),
    run_id: ref,
    status: z.enum(["running", "completed", "failed", "cancelled"]),
    steps: z.number().int().nonnegative(),
    stage: z.string().max(120).nullable(),
    name: z.string().max(120).nullable(),
  })
  .strict();
export type RunProgress = z.infer<typeof runProgressSchema>;

export const runSummarySchema = z
  .object({
    run_id: ref,
    turn_id: ref,
    question: bounded,
    status: z.enum(["running", "completed", "failed", "cancelled"]),
    answer_status: z.enum(["accepted", "qualified", "abstained"]).nullable(),
    error: z.string().nullable(),
    result_ref: ref.nullable(),
    duration_ms: z.number().int().nonnegative(),
    started_at: z.iso.datetime({ offset: true }),
    ended_at: z.iso.datetime({ offset: true }).nullable(),
    events: z.number().int().nonnegative(),
  })
  .strict();
export const runListSchema = z
  .object({
    api_version: z.literal(1),
    runs: z.array(runSummarySchema).max(200),
  })
  .strict();
export const traceStepSchema = z
  .object({
    sequence: z.number().int().min(1),
    stage: z.string().max(120),
    name: z.string().max(120),
    status: z.string().max(120),
    started_ms: z.number().int().nonnegative(),
    duration_ms: z.number().int().nonnegative(),
    attributes: z.record(z.string(), z.unknown()),
    // A long detail arrives as a preview; the step route returns all of it.
    detail: z.string().max(16384).nullable(),
    parent: z.number().int().min(1).nullable(),
    detail_chars: z.number().int().nonnegative().nullable().optional(),
    detail_complete: z.boolean().optional(),
  })
  .strict();
export const traceStepFullSchema = z
  .object({
    api_version: z.literal(1),
    sequence: z.number().int().min(1),
    name: z.string().max(120),
    detail: z.string().max(2_000_000).nullable(),
  })
  .strict();
export const runDetailSchema = z
  .object({
    api_version: z.literal(1),
    run: runSummarySchema,
    steps: z.array(traceStepSchema).max(5000),
  })
  .strict();
export type RunSummary = z.infer<typeof runSummarySchema>;
export type RunDetail = z.infer<typeof runDetailSchema>;
export type TraceStep = z.infer<typeof traceStepSchema>;
export type TraceStepFull = z.infer<typeof traceStepFullSchema>;

export const searchTrialSchema = z
  .object({
    api_version: z.literal(1),
    query: z.string().max(512),
    status: z.string().max(40),
    clarification_required: z.boolean(),
    total_candidates: z.number().int().min(0),
    hits: z
      .array(
        z
          .object({
            series_id: z.string().max(200),
            title: z.string().max(400),
            provider: z.string().max(200),
            unit: z.string().max(200).nullable(),
            frequency: z.string().max(40),
            stock_flow: z.string().max(40),
            prepared: z.boolean(),
            archived: z.boolean(),
            stage: z.enum(["lexical", "dense", "both"]),
            concepts: z.array(z.string().max(120)).max(20),
          })
          .strict(),
      )
      .max(10),
    retrieval_mode: z.enum(["lexical_only", "hybrid", "lexical_degraded"]),
    dense_status: z.enum([
      "not_configured",
      "skipped_no_eligible",
      "success",
      "failed",
    ]),
    dense_failure: z
      .enum(["snapshot_mismatch", "embedding_failed", "index_failed"])
      .nullable(),
    embedding_model: z.string().max(200).nullable(),
    input_policy_id: z.string().max(120).nullable(),
    top_candidate: z
      .enum(["unambiguous", "ambiguous", "unconfirmed", "none"])
      .optional(),
  })
  .strict();
export type SearchTrial = z.infer<typeof searchTrialSchema>;

/** Which generation of meaning vectors this deployment searches, and what it covers. */
export const vectorIndexSchema = z
  .object({
    api_version: z.literal(1),
    configured: z.boolean(),
    model: z.string().max(200).nullable(),
    input_policy_id: z.string().max(120).nullable(),
    origin: z.string().max(60).nullable(),
    dimension: z.number().int().min(0),
    generation_sha256: z.string().max(64).nullable(),
    generation_version: z.string().max(120).nullable(),
    catalog_sha256: z.string().max(64),
    catalog_version: z.string().max(120),
    covers_catalog: z.boolean(),
    series_total: z.number().int().min(0),
    series_vectored: z.number().int().min(0),
    missing: z.array(z.string().max(200)).max(50),
    rebuilding: z.boolean(),
    rebuildable: z.boolean(),
    built_at: z.string().max(40).nullable(),
    last_error: z.string().max(120).nullable(),
  })
  .strict();
export type VectorIndex = z.infer<typeof vectorIndexSchema>;

// What re-reading the sources' own directories found (DEC-177).
export const directoryRefreshSchema = z
  .object({
    api_version: z.literal(1),
    evds_listed: z.number().int().min(0).max(10000),
    added_total: z.number().int().min(0).max(10000),
    added: z.array(z.string().max(240)).max(20),
    withdrawn: z.number().int().min(0).max(10000),
    series_lists_reread: z.number().int().min(0).max(10000),
    series_lists_failed: z.number().int().min(0).max(10000),
    catalog_changed: z.boolean(),
  })
  .strict();
export type DirectoryRefresh = z.infer<typeof directoryRefreshSchema>;

/** Reverse lineage: this browser's answers whose proof read the series. */
export const seriesUsesSchema = z
  .object({
    api_version: z.literal(1),
    series_id: z.string().max(200),
    uses: z
      .array(
        z
          .object({
            conversation_id: z.string().max(64),
            title: z.string().max(200),
            turn_id: z.string().max(64),
            question: z.string().max(500),
            used_at: z.string().max(40),
          })
          .strict(),
      )
      .max(200),
  })
  .strict();
export type SeriesUses = z.infer<typeof seriesUsesSchema>;

/** The sources model calls are assembled from; reading is the whole contract. */
export const promptPartsSchema = z
  .object({
    api_version: z.literal(1),
    parts: z
      .array(
        z
          .object({
            part_id: z.string().max(120),
            title: z.string().max(200),
            sent_when: z.string().max(300),
            content: z.string().max(20000),
            content_sha256: z.string().length(64),
          })
          .strict(),
      )
      .max(64),
  })
  .strict();
export type PromptParts = z.infer<typeof promptPartsSchema>;

export const runtimeSettingsSchema = z
  .object({
    api_version: z.literal(1),
    available: z.array(z.string().max(60)).max(16),
    disabled: z.array(z.string().max(60)).max(16),
    history_turns: z.number().int().min(0).max(64),
    max_history_turns: z.number().int().min(0).max(64),
    models: z.array(z.string().max(200)).default([]),
    model: z.string().max(200).nullable().optional(),
  })
  .strict();
export type RuntimeSettings = z.infer<typeof runtimeSettingsSchema>;

export const feedbackReasons = [
  "accuracy",
  "incomplete",
  "wrong_source",
  "slow",
  "lost_context",
  "unclear",
  "other",
] as const;
export const feedbackSchema = z
  .object({
    turn_id: ref,
    answer_digest: digest,
    run_id: ref.nullable(),
    result_version: digest.nullable(),
    rating: z.enum(["up", "down"]),
    comment: z.string().max(2000).nullable(),
    reasons: z.array(z.enum(feedbackReasons)).max(8),
    created_at: z.iso.datetime({ offset: true }),
    updated_at: z.iso.datetime({ offset: true }),
    score: z.number().int().min(1).max(5).nullable(),
  })
  .strict();
export const feedbackListSchema = z
  .object({
    api_version: z.literal(1),
    feedback: z.array(feedbackSchema).max(200),
  })
  .strict();
export type Feedback = z.infer<typeof feedbackSchema>;
export type FeedbackReason = (typeof feedbackReasons)[number];

// -- Knowledge base (DEC-157) -------------------------------------------------
const moment = z.iso.datetime({ offset: true });
const day = z.iso.date();
export const knowledgeSeriesSchema = z
  .object({
    series_id: z.string().max(200),
    title: z.string().max(1024),
    provider: z.string().max(200),
    // listed: from a source's own directory, never reviewed one by one (DEC-176).
    origin: z.enum(["reviewed", "listed", "user"]),
    status: z.enum(["active", "archived", "unknown"]),
    prepared: z.boolean(),
    fetchable: z.boolean(),
    unit: z.string().max(200).nullable(),
    scale: z.string().max(40),
    frequency: z.string().max(40),
    stock_flow: z.string().max(40),
    cumulative: z.string().max(40),
    base_year: z.number().int().nullable(),
    coverage_start: day.nullable(),
    coverage_end: day.nullable(),
    observations: z.number().int().nonnegative().nullable(),
    aliases: z.array(z.string().max(120)).max(10),
    note: z.string().max(1000).nullable(),
    version: z.number().int().positive().nullable(),
    slug: z.string().max(40).nullable(),
    updated_at: moment.nullable(),
    acquired_at: moment.nullable(),
    // What catalogue search reads for the entry (DEC-171); absent on an older server.
    description: z.string().max(8192).nullable().optional(),
    labels: z.array(z.string().max(1024)).max(40).optional(),
    reviewed_aliases: z.array(z.string().max(400)).max(400).optional(),
    reviewer_note: z.string().max(8192).nullable().optional(),
    search_text: z.string().max(16384).nullable().optional(),
    geography: z.string().max(200).nullable().optional(),
  })
  .strict();
export const knowledgeListSchema = z
  .object({
    api_version: z.literal(1),
    catalog_digest: z.string().regex(/^[a-f0-9]{64}$/),
    reviewed_digest: z.string().regex(/^[a-f0-9]{64}$/),
    // Mirrors MAX_CATALOG_SERIES: a guard against a malformed body, not a catalog size.
    series: z.array(knowledgeSeriesSchema).max(10000),
    // Directory entries search finds and turns fetch on first use; absent on an older server.
    listed_series: z.number().int().min(0).max(10000).optional(),
    total: z.number().int().min(0).max(10000).nullable().optional(),
    page: z.number().int().min(1).nullable().optional(),
    page_size: z.number().int().min(1).max(100).nullable().optional(),
    counts: z.record(z.string(), z.number().int().min(0)).nullable().optional(),
    provinces: z.array(z.string().max(200)).max(128).optional(),
  })
  .strict();
export const datasetDetailSchema = z
  .object({
    api_version: z.literal(1),
    series: knowledgeSeriesSchema,
    source_kind: z.enum(["upload", "manual"]),
    description: z.string().max(1000).nullable(),
    aggregation: z.string().max(40),
    weekly_anchor: z.string().max(20).nullable().optional(),
    observations: z
      .array(
        z
          .object({
            period_start: day,
            period_end: day,
            value: z.number().finite().nullable(),
          })
          .strict(),
      )
      .max(5000),
    history: z
      .array(
        z
          .object({
            version: z.number().int().positive(),
            status: z.enum(["active", "archived"]),
            observations: z.number().int().nonnegative(),
            content_sha256: z.string().regex(/^[a-f0-9]{64}$/),
            created_at: moment,
          })
          .strict(),
      )
      .max(500),
  })
  .strict();
export const noteHistorySchema = z
  .object({
    api_version: z.literal(1),
    series_id: z.string().max(200),
    history: z
      .array(
        z
          .object({
            version: z.number().int().positive(),
            archived: z.boolean(),
            aliases: z.array(z.string().max(120)).max(10),
            note: z.string().max(1000).nullable(),
            created_at: moment,
          })
          .strict(),
      )
      .max(500),
  })
  .strict();
export type KnowledgeSeries = z.infer<typeof knowledgeSeriesSchema>;
export type KnowledgeList = z.infer<typeof knowledgeListSchema>;
export type DatasetDetail = z.infer<typeof datasetDetailSchema>;
/**
 * A saved knowledge base: the listing as read, plus each user dataset's full
 * detail (observations and declared meaning), so the file can be imported
 * elsewhere by replaying the same versioned writes. Nothing reviewed travels:
 * the reviewed catalogue is the deployment's own.
 */
export const knowledgeExportSchema = z
  .object({
    schema: z.literal("kkb-knowledge-export-v1"),
    exported_at: z.string().max(40),
    listing: knowledgeListSchema,
    datasets: z.array(datasetDetailSchema).max(5000),
  })
  .strict();
export type KnowledgeExport = z.infer<typeof knowledgeExportSchema>;
export type NoteHistory = z.infer<typeof noteHistorySchema>;
export type DatasetRequest = {
  slug: string;
  title: string;
  description?: string;
  unit: string;
  scale: "one" | "thousand" | "million" | "billion";
  frequency: "weekly" | "monthly" | "quarterly" | "annual";
  weekly_anchor?:
    | "monday"
    | "tuesday"
    | "wednesday"
    | "thursday"
    | "friday"
    | "saturday"
    | "sunday";
  stock_flow: "stock" | "flow" | "rate" | "index";
  cumulative: "none" | "yearly_reset" | "since_inception";
  aggregation: "sum" | "average" | "first" | "last" | "min" | "max";
  base_year?: number;
  aliases: string[];
  observations?: { period_end: string; value: number | null }[];
  document?: {
    session_id: string;
    document_ref: string;
    period_column: string;
    value_column: string;
    sheet?: string;
    year?: number;
  };
};
export const seriesValuesSchema = z
  .object({
    api_version: z.literal(1),
    series_id: z.string().max(200),
    observations: z
      .array(
        z
          .object({
            period_start: day,
            period_end: day,
            value: z.number().finite().nullable(),
          })
          .strict(),
      )
      .max(5000),
  })
  .strict();
