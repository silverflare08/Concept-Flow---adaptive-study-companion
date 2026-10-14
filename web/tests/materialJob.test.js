import test from "node:test";
import assert from "node:assert/strict";
import { waitForMaterialJob } from "../src/materialJob.js";

test("material preparation waits through reading and indexing", async () => {
  const statuses = [
    { status: "running", stage: "reading" },
    { status: "running", stage: "indexing" },
    { status: "complete", stage: "ready", source: { chunks: 12 } },
  ];
  const stages = [], waits = [];
  const job = await waitForMaterialJob("", "job", item => stages.push(item.stage),
    async () => ({ ok: true, json: async () => ({ job: statuses.shift() }) }),
    async ms => waits.push(ms));
  assert.deepEqual(stages, ["reading", "indexing", "ready"]);
  assert.equal(waits.length, 2);
  assert.equal(job.source.chunks, 12);
});

test("cancelled or failed reading releases the loader with an error", async () => {
  for (const status of ["cancelled", "failed"]) {
    await assert.rejects(waitForMaterialJob("", "job", null,
      async () => ({ ok: true, json: async () => ({ job: { status, error: "Stopped" } }) })), /Stopped/);
  }
});
