import React, { useEffect, useRef, useState } from "react";
import { SlidersHorizontal, Pencil, Pin, PinOff, Trash2 } from "lucide-react";

export default function LibraryItemMenu({ item, kind, onPin, onRename, onDelete }) {
  const [open, setOpen] = useState(false);
  const root = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const close = event => !root.current?.contains(event.target) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);
  function run(action) { setOpen(false); action(); }
  return <div ref={root} className="relative shrink-0">
    <button onClick={event => { event.stopPropagation(); setOpen(current => !current); }} title="Item options" aria-label={`Manage ${kind} ${item.name || item.title}`} aria-expanded={open} className={`grid h-7 w-7 place-items-center rounded-lg border transition ${open ? "border-lavender bg-lilac text-plum" : "border-transparent bg-white/40 text-slate-400 hover:border-lavender hover:bg-lilac hover:text-plum"}`}><SlidersHorizontal size={14}/></button>
    {open && <div className="absolute right-0 top-9 z-50 w-40 overflow-hidden rounded-2xl border border-white bg-[#fbfaff] p-1.5 text-xs shadow-xl">
      <button onClick={() => run(() => onPin(item))} className="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left font-semibold text-slate-600 hover:bg-lilac/50">{item.pinned ? <PinOff size={15}/> : <Pin size={15}/>} {item.pinned ? "Unpin" : "Pin to top"}</button>
      <button onClick={() => run(() => onRename(item))} className="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left font-semibold text-slate-600 hover:bg-lilac/50"><Pencil size={15}/> Rename</button>
      <button onClick={() => run(() => onDelete(item))} className="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left font-semibold text-rose-600 hover:bg-rose-50"><Trash2 size={15}/> {kind === "course" ? "Archive" : "Delete"}</button>
    </div>}
  </div>;
}
