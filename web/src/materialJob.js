// Resolve only when the material is indexed, not merely received by the server.
export async function waitForMaterialJob(api, jobId, onUpdate, fetchImpl = fetch, pause = ms => new Promise(resolve => setTimeout(resolve, ms))) {
  while (true) {
    const response = await fetchImpl(`${api}/api/material-jobs/${encodeURIComponent(jobId)}`);
    const data = await response.json();
    if (!response.ok || !data.job) throw new Error(data.detail || "Could not check material processing status.");
    const job = data.job;
    onUpdate?.(job);
    if (job.status === "complete") return job;
    if (job.status !== "running") throw new Error(job.error || "Material could not be processed.");
    await pause(750);
  }
}
