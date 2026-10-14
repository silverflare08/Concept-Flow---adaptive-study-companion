import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { NotebookPen, X } from "lucide-react";

export default function MaterialNotes({ api, source }) {
  const [notes, setNotes] = useState(source.notes || "");
  const [saved, setSaved] = useState(source.notes || "");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [open, setOpen] = useState(false);
  const trigger = useRef(null);
  function close() { setOpen(false); trigger.current?.focus(); }
  useEffect(() => {
    if (!open) return;
    function handleKey(event) {
      if (event.key === "Escape") { event.stopPropagation(); close(); }
      if (event.key === "Tab") {
        const dialog = document.getElementById(`notes-dialog-${source.id}`);
        const controls = [...(dialog?.querySelectorAll('button:not(:disabled), textarea') || [])];
        const first = controls[0], last = controls[controls.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, source.id]);
  async function save() {
    setBusy(true); setMessage("");
    try {
      const response = await fetch(`${api}/api/materials/${source.id}/notes`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ notes }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not save notes.");
      setSaved(data.notes); setMessage("Notes saved.");
    } catch (issue) { setMessage(issue.message); } finally { setBusy(false); }
  }
  return <>
    <button ref={trigger} type="button" onClick={() => setOpen(true)} title={saved ? "Edit material notes" : "Add material notes"} aria-label={`Notes for ${source.name}`} aria-haspopup="dialog" className={`icon-button ${saved ? "bg-lilac text-plum" : "text-slate-600"}`}><NotebookPen size={16}/></button>
    {open && createPortal(<div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/35 p-4 backdrop-blur-sm">
      <section id={`notes-dialog-${source.id}`} role="dialog" aria-modal="true" aria-labelledby={`notes-title-${source.id}`} className="w-full max-w-xl rounded-3xl bg-[#fbfaff] p-5 shadow-2xl">
        <div className="flex items-center justify-between gap-3"><h2 id={`notes-title-${source.id}`} className="flex items-center gap-2 text-lg font-bold text-plum"><NotebookPen size={20}/>My notes</h2><button onClick={close} aria-label="Close notes" className="icon-button"><X size={18}/></button></div>
        <p className="mt-1 truncate text-xs text-slate-500">{source.name}</p>
        <textarea autoFocus aria-label={`Notes for ${source.name}`} maxLength={20000} rows={7} value={notes} onChange={e => { setNotes(e.target.value); setMessage(""); }} placeholder="Write your questions, reminders or revision notes for this material…" className="mt-4 w-full resize-y rounded-xl border border-slate-200 bg-white p-3 text-sm outline-none focus:border-plum"/>
        <div className="mt-3 flex items-center gap-3"><button onClick={save} disabled={busy || notes === saved} className="primary-button text-xs disabled:opacity-50">{busy ? "Saving…" : "Save notes"}</button><span role="status" className="text-xs text-slate-500">{message || (notes !== saved ? "Unsaved changes" : "Saved notes are stored with this material.")}</span></div>
      </section>
    </div>, document.body)}
  </>;
}
