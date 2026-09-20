/** A run can finish between the first conversation read and the run-list read. */
export function hasUnrecordedRun(
  runs: { turn_id: string }[],
  messages: { turn_id: string }[],
): boolean {
  const recorded = new Set(messages.map((message) => message.turn_id));
  return runs.some((run) => !recorded.has(run.turn_id));
}

/**
 * A known server error must not erase a submitted prompt from the visible turn list.
 *
 * What it says next to the prompt depends on how far it got: a question the
 * server never admitted was not run at all, while an admitted turn was cut short
 * by the restart and left a trace. Marking both "not_found" said "no session"
 * about a question that never left this tab (finding J-5).
 */
export function keepSubmittedPrompts<
  T extends {
    turn?: { state: string };
    turn_id?: string;
    admission_error?: string;
  },
>(items: T[]): T[] {
  return items.map((item) =>
    item.turn?.state === "completed" || item.turn?.state === "failed"
      ? item
      : {
          ...item,
          admission_error:
            item.turn || item.turn_id ? "turn_interrupted" : "turn_not_sent",
        },
  );
}

/**
 * Stored messages whose published table this browser does not hold yet.
 *
 * A table published while a turn is running cannot be read back (the runner
 * answers "busy"), so the answer must be asked for again rather than explained
 * away as a restart. `lost` are the receipts a free runner already refused.
 */
export function unreadTables<T extends { result_ref?: string | null }>(
  messages: T[],
  restored: { result: { result_ref: string } }[],
  lost: string[],
): T[] {
  const held = new Set(restored.map((entry) => entry.result.result_ref));
  return messages.filter(
    (message) =>
      Boolean(message.result_ref) &&
      !held.has(message.result_ref as string) &&
      !lost.includes(message.result_ref as string),
  );
}
