const active = new Map();
const jobs = new Map();
const listeners = new Set();
const update = () => listeners.forEach(listener => listener());
export const subscribeGeneration = listener => { listeners.add(listener); return () => listeners.delete(listener); };
export const generationCount = () => active.size + jobs.size;

export function reportGenerationJob(jobId, base, status) {
  if (!jobId) return;
  if (status === "running") jobs.set(jobId, { base });
  else jobs.delete(jobId);
  update();
}

export async function generationFetch(url, options = {}) {
  options = { credentials: "include", ...options };
  const tracked = options.method === "POST" && /\/api\/(tutor(?:$|\/overview$)|study-guide\/generate|course-map\/generate|assessments(?:$|\/[^/]+\/submit$)|materials(?:$|\/url$))/.test(String(url));
  const id = tracked ? crypto.randomUUID() : null;
  const controller = tracked ? new AbortController() : null;
  const base = String(url).split("/api/")[0];
  if (id) { active.set(id, { controller, base }); update(); }
  try {
    const response = await window.fetch(url, tracked ? { ...options, signal: controller.signal, headers: { ...options.headers, "X-Generation-Id": id } } : options);
    if (response.status === 401) window.dispatchEvent(new Event("conceptflow-session-expired"));
    if (response.ok && response.headers.get("content-type")?.includes("application/json")) {
      const data = await response.clone().json();
      if (data.job?.job_id) {
        reportGenerationJob(data.job.job_id, base, data.job.status);
      }
      for (const report of data.reports || []) {
        if (report.job_id) reportGenerationJob(report.job_id, base, report.status === "processing" ? "running" : report.status);
      }
    }
    return response;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("Stopped by you.");
    throw error;
  } finally { if (id) { active.delete(id); update(); } }
}

export async function stopGenerations() {
  const pending = [];
  for (const [id, request] of active) {
    pending.push(window.fetch(`${request.base}/api/generation/${id}/stop`, { method: "POST", credentials: "include" }));
  }
  for (const [id, job] of jobs) pending.push(window.fetch(`${job.base}/api/jobs/${id}/stop`, { method: "POST", credentials: "include" }));
  const responses = await Promise.all(pending);
  if (responses.some(response => !response.ok)) throw new Error("Could not stop generation. Check the API connection.");
  for (const request of active.values()) request.controller.abort();
  active.clear(); jobs.clear(); update();
}
