import React, { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { FileText, X } from "lucide-react";
import DownloadMenu from "./DownloadMenu.jsx";

export default function TranscriptDialog({ api, source, onClose }) {
  const [transcript, setTranscript] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    fetch(`${api}/api/materials/${source.id}/transcript`, { signal: controller.signal, cache: "no-store" })
      .then(async response => { const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Could not load transcript."); return data; })
      .then(setTranscript).catch(issue => { if (issue.name !== "AbortError") setError(issue.message); });
    const close = event => { if (event.key === "Escape") onClose(); };
    document.addEventListener("keydown", close);
    return () => { controller.abort(); document.removeEventListener("keydown", close); };
  }, [api, source.id]);
  return createPortal(<div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/35 p-4 backdrop-blur-sm">
    <section role="dialog" aria-modal="true" aria-labelledby="transcript-title" className="flex max-h-[85vh] w-full max-w-3xl flex-col rounded-3xl bg-[#fbfaff] p-5 shadow-2xl">
      <div className="flex items-center justify-between gap-3"><h2 id="transcript-title" className="flex items-center gap-2 text-lg font-bold"><FileText size={20} className="text-plum"/>Lecture Transcript</h2><button autoFocus onClick={onClose} aria-label="Close transcript" className="icon-button"><X size={18}/></button></div>
      <p className="mt-1 truncate text-xs text-slate-500" title={source.name}>{source.name}</p>
      <p className="mt-3 text-xs leading-5 text-slate-500">Original-language speech, organised by timestamp. Not a summary or Hinglish translation. Recognition errors may remain.</p>
      {transcript && <div className="mt-3"><DownloadMenu href={`${api}/api/materials/${source.id}/transcript/download`} label="Download transcript"/></div>}
      <div className="mt-4 min-h-0 overflow-y-auto overscroll-contain pr-2">
        {error && <p role="alert" className="rounded-xl bg-peach p-3 text-sm">{error}</p>}
        {!transcript && !error && <p role="status" className="text-sm text-slate-500">Opening the stored transcript… No new AI generation is needed.</p>}
        {transcript?.entries.map((entry, index) => { const href = entry.target_uri?.startsWith("/") ? `${api}${entry.target_uri}` : entry.target_uri;
          return <section key={index} className="mb-4 rounded-xl bg-white p-4"><a href={href} target="_blank" rel="noreferrer" className="text-[11px] font-semibold text-plum underline underline-offset-2">{entry.timestamp}</a><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">{entry.text}</p></section>;
        })}
      </div>
    </section>
  </div>, document.body);
}
