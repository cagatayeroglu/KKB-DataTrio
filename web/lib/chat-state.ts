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
