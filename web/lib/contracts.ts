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
    samples: z
      .object({
        used: z.number().int().nonnegative(),
        missing: z.number().int().nonnegative(),
        excluded: z.number().int().nonnegative(),
        minimum_required: z.number().int().nonnegative().nullable(),
      })
      .strict()
      .nullable(),
    lag: z.number().int().nullable(),
  })
  .strict();
export const resultSchema = z
  .object({
    result_ref: ref,
    version: z.string().regex(/^[a-f0-9]{64}$/),
    kind: z.string(),
    claim_kind: z.string(),
    published: z.literal(true),
    cells: z.array(cellSchema).max(2048),
    proof_graph: z.literal("unavailable"),
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
  .strict();
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
export type Turn = z.infer<typeof turnSchema>;
export type Session = z.infer<typeof sessionSchema>;
export type Dataset = z.infer<typeof datasetSchema>;
export type Health = z.infer<typeof healthSchema>;

export const savedSchema = z
  .object({
    session: sessionSchema,
    turns: z
      .array(
        z
          .object({
            request_id: ref,
            question: z.string().min(1).max(4096),
            turn_id: ref.optional(),
          })
          .strict(),
      )
      .max(24),
  })
  .strict();
export type Saved = z.infer<typeof savedSchema>;
