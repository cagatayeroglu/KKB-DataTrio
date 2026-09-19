import test from "node:test";
import assert from "node:assert/strict";
import { modelCallLabel } from "../lib/trace-summary";

test("a running first planner call is not presented as zero model calls", () => {
  assert.match(
    modelCallLabel("running", [{ stage: "request", name: "turn.received" }]),
    /sürüyor veya bekleniyor/,
  );
  assert.doesNotMatch(modelCallLabel("running", []), /0 model çağrısı/);
});

test("only completed provider spans count, not plan outputs or rejections", () => {
  const steps = [
    { stage: "planning", name: "planner.initial" },
    { stage: "planning", name: "planner.output" },
    { stage: "planning", name: "plan.rejected" },
    { stage: "answer", name: "writer.call" },
  ];
  assert.equal(
    modelCallLabel("completed", steps),
    "2 tamamlanan model çağrısı",
  );
});
