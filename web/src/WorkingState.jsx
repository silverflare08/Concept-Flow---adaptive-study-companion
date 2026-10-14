import React from "react";
import { BookOpen, Sparkles } from "lucide-react";

export default function WorkingState({ title, detail, progress = null }) {
  return <div className="working-card" role="status" aria-live="polite">
    <div className="study-orbit" aria-hidden="true">
      <span className="study-orbit-track"/>
      <span className="study-orbit-core"><BookOpen size={21}/></span>
      <span className="study-orbit-ring"><i/><i/><i/></span>
    </div>
    <div className="min-w-0 flex-1">
      <p className="flex items-center gap-2 font-bold text-slate-800">{title}<Sparkles size={15} className="text-plum"/></p>
      <p className="mt-1 text-sm leading-5 text-slate-600">{detail}</p>
      {progress != null && <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/80" role="progressbar" aria-label={title} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(Math.min(100, Math.max(0, progress)))}>
        <div className="h-full rounded-full bg-gradient-to-r from-plum to-[#b9a5da] transition-all duration-500" style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}/>
      </div>}
      {progress == null && <div className="study-loading-line" aria-hidden="true"><span/></div>}
    </div>
  </div>;
}
