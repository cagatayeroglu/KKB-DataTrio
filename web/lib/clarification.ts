/** The card fills the composer; the server decides whether this answers a pending question. */
export function clarificationPickText(
  entry: { title: string; detail: string },
  asking: boolean,
): string {
  const name = `${entry.title} (${entry.detail})`;
  return asking ? name : `Aynı isteği bu kez şu kayıtla yap: ${name}`;
}
