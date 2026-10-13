import React, { useEffect } from "react";
import { AlertTriangle, LoaderCircle, X } from "lucide-react";

export default function ConfirmDialog({ open, title, body, confirmLabel = "Delete", busy = false, onConfirm, onCancel }) {
  useEffect(() => {
    if (!open) return undefined;
    function closeOnEscape(event) { if (event.key === "Escape" && !busy) onCancel(); }
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [open, busy, onCancel]);
  if (!open) return null;
  return <div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/30 p-4 backdrop-blur-sm" role="presentation" onMouseDown={event => event.target === event.currentTarget && !busy && onCancel()}>
    <section role="alertdialog" aria-modal="true" aria-labelledby="confirm-title" aria-describedby="confirm-body" className="w-full max-w-md rounded-3xl border border-white/80 bg-[#fbfaff] p-6 shadow-2xl">
      <div className="flex items-start justify-between gap-4"><div className="grid h-11 w-11 place-items-center rounded-2xl bg-rose-50 text-rose-500"><AlertTriangle size={22}/></div><button disabled={busy} onClick={onCancel} aria-label="Close confirmation" className="icon-button text-slate-500 disabled:opacity-50"><X size={18}/></button></div>
      <h2 id="confirm-title" className="mt-5 text-xl font-extrabold text-slate-800">{title}</h2>
      <p id="confirm-body" className="mt-2 text-sm leading-6 text-slate-600">{body}</p>
      <div className="mt-6 flex justify-end gap-3"><button disabled={busy} onClick={onCancel} className="secondary-button disabled:opacity-50">Cancel</button><button disabled={busy} onClick={onConfirm} className="inline-flex items-center gap-2 rounded-xl bg-rose-500 px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-rose-200 transition hover:bg-rose-600 disabled:cursor-wait disabled:opacity-90">{busy && <LoaderCircle className="animate-spin" size={16}/>} {busy ? "Deleting…" : confirmLabel}</button></div>
    </section>
  </div>;
}
