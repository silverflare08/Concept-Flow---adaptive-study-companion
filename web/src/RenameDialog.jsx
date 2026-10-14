import React, { useEffect, useState } from "react";
import { Pencil, X } from "lucide-react";

export default function RenameDialog({ target, busy = false, onSave, onCancel }) {
  const [value, setValue] = useState("");
  useEffect(() => { setValue(target?.name || target?.title || ""); }, [target]);
  useEffect(() => {
    if (!target) return undefined;
    const close = event => event.key === "Escape" && !busy && onCancel();
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [target, busy, onCancel]);
  if (!target) return null;
  return <div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/25 p-4 backdrop-blur-sm" onMouseDown={event => event.target === event.currentTarget && !busy && onCancel()}>
    <section role="dialog" aria-modal="true" aria-labelledby="rename-title" className="w-full max-w-md rounded-3xl border border-white/80 bg-[#fbfaff] p-6 shadow-2xl">
      <div className="flex items-center justify-between"><div className="grid h-11 w-11 place-items-center rounded-2xl bg-lilac text-plum"><Pencil size={20}/></div><button disabled={busy} onClick={onCancel} aria-label="Close rename dialog" className="icon-button"><X size={18}/></button></div>
      <h2 id="rename-title" className="mt-5 text-xl font-extrabold">Rename {target.kind === "course" ? "course" : "chat"}</h2>
      <p className="mt-2 text-sm text-slate-500">Use a short name that will be easy to recognise later.</p>
      <input autoFocus value={value} onChange={event => setValue(event.target.value)} onKeyDown={event => event.key === "Enter" && value.trim() && onSave(value.trim())} className="mt-5 w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none focus:border-plum" maxLength={120}/>
      <div className="mt-6 flex justify-end gap-3"><button disabled={busy} onClick={onCancel} className="secondary-button">Cancel</button><button disabled={busy || !value.trim()} onClick={() => onSave(value.trim())} className="primary-button disabled:opacity-50">{busy ? "Saving…" : "Save name"}</button></div>
    </section>
  </div>;
}
