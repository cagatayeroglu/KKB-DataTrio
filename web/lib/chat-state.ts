/** A run can finish between the first conversation read and the run-list read. */
export function hasUnrecordedRun(
  runs: { turn_id: string }[],
  messages: { turn_id: string }[],
): boolean {
  const recorded = new Set(messages.map((message) => message.turn_id));
  return runs.some((run) => !recorded.has(run.turn_id));
}

/** A known server error must not erase a submitted prompt from the visible turn list. */
export function keepSubmittedPrompts<
  T extends { turn?: { state: string }; admission_error?: string },
>(items: T[]): T[] {
  return items.map((item) =>
    item.turn?.state === "completed" || item.turn?.state === "failed"
      ? item
      : { ...item, admission_error: "not_found" },
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
