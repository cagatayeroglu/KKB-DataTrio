import test from "node:test";
import assert from "node:assert/strict";
import { clarificationPickText } from "../lib/clarification";

test("offered series card copies its exact title into the composer without losing detail", () => {
  const entry = {
    title: "Konut Kredisi (TL, Akım, %)",
    detail:
      "Kredi Faiz Oranları (Akım), EVDS/Mevduat, Kalkınma ve Yatırım Bankaları, haftalık, percent, oran",
  };
  assert.equal(
    clarificationPickText(entry, true),
    `${entry.title} (${entry.detail})`,
  );
  assert.equal(
    clarificationPickText(entry, false),
    `Aynı isteği bu kez şu kayıtla yap: ${entry.title} (${entry.detail})`,
  );
});
