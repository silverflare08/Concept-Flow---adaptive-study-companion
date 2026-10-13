import React from "react";
import { LoaderCircle, Sparkles } from "lucide-react";

export default function WorkingState({ title, detail, progress = null }) {
  return <div className="working-card" role="status" aria-live="polite">
    <div className="relative grid h-12 w-12 shrink-0 place-items-center">
      <span className="absolute inset-0 animate-ping rounded-full bg-lilac/70"/>
      <span className="relative grid h-10 w-10 place-items-center rounded-full bg-white text-plum shadow-sm">
        <LoaderCircle className="animate-spin" size={21}/>
      </span>
    </div>
    <div className="min-w-0 flex-1">
      <p className="flex items-center gap-2 font-bold text-slate-800">{title}<Sparkles size={15} className="text-plum"/></p>
      <p className="mt-1 text-sm leading-5 text-slate-600">{detail}</p>
      {progress && <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/80">
        <div className="h-full rounded-full bg-plum transition-all duration-500" style={{ width: `${Math.max(8, progress)}%` }}/>
      </div>}
      {!progress && <div className="mt-3 flex gap-1.5" aria-hidden="true">
        {[0, 1, 2].map(index => <span key={index} className="working-dot" style={{ animationDelay: `${index * 180}ms` }}/>) }
      </div>}
    </div>
  </div>;
}
