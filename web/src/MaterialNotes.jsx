import React, { useState } from "react";
import { NotebookPen } from "lucide-react";

export default function MaterialNotes({ api, source }) {
  const [notes, setNotes] = useState(source.notes || "");
  const [saved, setSaved] = useState(source.notes || "");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function save() {
    setBusy(true); setMessage("");
    try {
      const response = await fetch(`${api}/api/materials/${source.id}/notes`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ notes }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not save notes.");
      setSaved(data.notes); setMessage("Notes saved.");
    } catch (issue) { setMessage(issue.message); } finally { setBusy(false); }
  }
  return <details className="mt-2 rounded-xl border border-lavender/40 bg-white/70 px-3 py-2"><summary className="cursor-pointer text-xs font-semibold text-plum"><span className="inline-flex items-center gap-1.5"><NotebookPen size={14}/>My notes {saved && "· saved"}</span></summary><textarea aria-label={`Notes for ${source.name}`} maxLength={20000} rows={4} value={notes} onChange={e => { setNotes(e.target.value); setMessage(""); }} placeholder="Write your questions, reminders or revision notes for this material…" className="mt-3 w-full resize-y rounded-lg border border-slate-200 bg-white p-3 text-sm outline-none focus:border-plum"/><div className="mt-2 flex items-center gap-3"><button onClick={save} disabled={busy || notes === saved} className="primary-button py-1.5 text-xs disabled:opacity-50">{busy ? "Saving…" : "Save notes"}</button><span role="status" className="text-xs text-slate-500">{message || (notes !== saved ? "Unsaved changes" : "")}</span></div></details>;
}
