import test from "node:test";
import assert from "node:assert/strict";
import {
  hasUnrecordedRun,
  keepSubmittedPrompts,
  unreadTables,
} from "../lib/chat-state";

test("a run finishing across the history snapshot boundary triggers a fresh read", () => {
  const messages = [{ turn_id: "earlier" }];
  assert.equal(hasUnrecordedRun([{ turn_id: "earlier" }], messages), false);
  assert.equal(hasUnrecordedRun([{ turn_id: "new" }], messages), true);
});

test("lost server session keeps submitted prompt and completed entries visible", () => {
  const entries: {
    question: string;
    turn?: { state: string };
    admission_error?: "not_found";
  }[] = [
    { question: "pending exact question" },
    { question: "trusted earlier question", turn: { state: "completed" } },
  ];
  const visible = keepSubmittedPrompts(entries);
  assert.equal(visible[0].question, "pending exact question");
  assert.equal(visible[0].admission_error, "not_found");
  assert.deepEqual(visible[1], entries[1]);
});

test("a published table missing from this browser is asked for again, once", () => {
  const messages = [
    { result_ref: "held" },
    { result_ref: "busy-earlier" },
    { result_ref: "gone" },
    { result_ref: null },
  ];
  const restored = [{ result: { result_ref: "held" } }];
  assert.deepEqual(unreadTables(messages, restored, ["gone"]), [
    { result_ref: "busy-earlier" },
  ]);
  // Once it arrives, nothing is asked for again.
  assert.deepEqual(
    unreadTables(
      messages,
      [...restored, { result: { result_ref: "busy-earlier" } }],
      ["gone"],
    ),
    [],
  );
});
