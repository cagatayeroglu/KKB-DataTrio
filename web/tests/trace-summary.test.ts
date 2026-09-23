import test from "node:test";
import assert from "node:assert/strict";
import {
  liveActivityLabel,
  modelCallLabel,
  runReadMessage,
} from "../lib/trace-summary";

test("failed trace reads never look empty or indefinitely starting", () => {
  assert.equal(runReadMessage("error", 0), "Kayıtlar okunamadı — yeniden dene");
  assert.equal(runReadMessage("ready", 0), "Bu sohbette kayıtlı işlem yok.");
  assert.equal(runReadMessage("loading", 0), "Kayıtlar yükleniyor…");
  assert.equal(runReadMessage("ready", 1), null);
  assert.match(liveActivityLabel("", true), /yeniden deneniyor/);
  assert.equal(
    liveActivityLabel("Plan hazırlanıyor", false),
    "Plan hazırlanıyor",
  );
});

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

test("a model call in flight is counted, not reported as nothing", () => {
  const steps = [
    { stage: "context", name: "context.assembled" },
    { stage: "model", name: "model.started" },
  ];
  assert.equal(modelCallLabel("running", steps), "1. model çağrısı sürüyor");
  const second = [
    ...steps,
    { stage: "planning", name: "planner.initial" },
    { stage: "model", name: "model.started" },
  ];
  assert.equal(
    modelCallLabel("running", second),
    "1 tamamlanan model çağrısı · 2. çağrı sürüyor",
  );
  assert.equal(
    modelCallLabel("completed", second),
    "1 tamamlanan model çağrısı",
  );
});
