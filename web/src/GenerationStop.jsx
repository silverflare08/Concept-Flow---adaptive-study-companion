import React, { useEffect, useState } from "react";
import { Square } from "lucide-react";
import { generationCount, subscribeGeneration, stopGenerations } from "./generationFetch.js";

export default function GenerationStop() {
  const [count, setCount] = useState(generationCount());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => subscribeGeneration(() => setCount(generationCount())), []);
  if (!count) return null;
  async function stop() {
    setBusy(true); setError("");
    try { await stopGenerations(); } catch (issue) { setError(issue.message); } finally { setBusy(false); }
  }
  return <div className="fixed bottom-5 right-5 z-40 rounded-2xl border border-lavender bg-[#fbfaff] p-2 shadow-lg"><button onClick={stop} disabled={busy} className="inline-flex items-center gap-2 rounded-xl px-3 py-2 text-xs font-bold text-plum hover:bg-lilac"><Square size={13} fill="currentColor"/>{busy ? "Stopping…" : `Stop ${count > 1 ? "active tasks" : "generating"}`}</button>{error && <p role="alert" className="max-w-60 p-2 text-xs text-rose-600">{error}</p>}</div>;
}
