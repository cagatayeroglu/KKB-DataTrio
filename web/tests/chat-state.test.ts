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
    turn_id?: string;
    admission_error?: string;
  }[] = [
    { question: "pending exact question" },
    {
      question: "admitted question",
      turn_id: "t1",
      turn: { state: "running" },
    },
    { question: "trusted earlier question", turn: { state: "completed" } },
  ];
  const visible = keepSubmittedPrompts(entries);
  assert.equal(visible[0].question, "pending exact question");
  // Never admitted: it was not run, so it does not claim a lost session.
  assert.equal(visible[0].admission_error, "turn_not_sent");
  // Admitted and cut short: it ran, and its trace says where it stopped.
  assert.equal(visible[1].admission_error, "turn_interrupted");
  assert.deepEqual(visible[2], entries[2]);
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
