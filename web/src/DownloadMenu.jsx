import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ChevronDown, Download, FileCode2, FileText, FileType2, Files } from "lucide-react";

const formats = [
  ["pdf", "PDF", FileText],
  ["docx", "Word", FileType2],
  ["txt", "Text", FileText],
  ["md", "Markdown", FileCode2],
  ["json", "JSON", Files],
];

export default function DownloadMenu({ href, label = "Download", compact = false }) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const buttonRef = useRef(null);
  const menuRef = useRef(null);

  function toggleMenu() {
    if (!open && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      const menuHeight = 238;
      const top = window.innerHeight - rect.bottom < menuHeight + 12 ? Math.max(8, rect.top - menuHeight - 8) : rect.bottom + 8;
      setPosition({ top, left: Math.max(8, Math.min(window.innerWidth - 184, rect.right - 176)) });
    }
    setOpen(value => !value);
  }

  useEffect(() => {
    if (!open) return undefined;
    const closeOutside = event => {
      if (!buttonRef.current?.contains(event.target) && !menuRef.current?.contains(event.target)) setOpen(false);
    };
    const closeOnEscape = event => { if (event.key === "Escape") setOpen(false); };
    const closeOnMove = () => setOpen(false);
    document.addEventListener("mousedown", closeOutside);
    document.addEventListener("keydown", closeOnEscape);
    window.addEventListener("resize", closeOnMove);
    window.addEventListener("scroll", closeOnMove, true);
    return () => {
      document.removeEventListener("mousedown", closeOutside);
      document.removeEventListener("keydown", closeOnEscape);
      window.removeEventListener("resize", closeOnMove);
      window.removeEventListener("scroll", closeOnMove, true);
    };
  }, [open]);

  return <div className="inline-block text-left">
    <button ref={buttonRef} type="button" onClick={toggleMenu} className={compact ? "icon-button" : "secondary-button"} title={compact ? label : undefined} aria-expanded={open}>
      <Download size={compact ? 16 : 17}/>{!compact && <>{label}<ChevronDown size={15}/></>}
    </button>
    {open && createPortal(<div ref={menuRef} style={position} className="fixed z-[9999] w-44 rounded-2xl border border-white/80 bg-white p-2 shadow-xl shadow-slate-300/30">
      <p className="px-2 pb-1 pt-1 text-[10px] font-bold uppercase tracking-[.12em] text-slate-400">Choose format</p>
      {formats.map(([format, name, Icon]) => <a key={format} onClick={() => setOpen(false)} href={`${href}${href.includes("?") ? "&" : "?"}format=${format}`} className="flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-lilac/55 hover:text-plum"><Icon size={16}/>{name}</a>)}
    </div>, document.body)}
  </div>;
}
