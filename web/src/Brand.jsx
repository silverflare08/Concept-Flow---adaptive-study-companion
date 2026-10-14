import React from "react";
import { BrainCircuit } from "lucide-react";
export default function Brand({ large = false, prominent = false }) {
  if (prominent) return <div className="flex flex-col items-center justify-center gap-4 text-center sm:flex-row sm:gap-5 sm:text-left"><div className="grid h-16 w-16 shrink-0 place-items-center rounded-2xl bg-plum text-white shadow-lg shadow-plum/15 sm:h-20 sm:w-20"><BrainCircuit size={42} aria-hidden="true"/></div><div><p className="font-brand text-[2.75rem] font-bold leading-none tracking-normal text-ink sm:text-[4rem] lg:text-[4.5rem]">ConceptFlow</p><p className="mt-3 text-sm tracking-wide text-slate-500">Study with clarity</p></div></div>;
  return <div className="flex items-center gap-3"><div className={`grid shrink-0 place-items-center rounded-2xl bg-plum text-white shadow-lg shadow-plum/20 ${large ? "h-14 w-14" : "h-11 w-11"}`}><BrainCircuit size={large ? 32 : 25} aria-hidden="true"/></div><div><p className={`font-brand font-bold tracking-normal ${large ? "text-3xl" : "text-[1.75rem]"}`}>ConceptFlow</p><p className="mt-0.5 text-xs text-slate-500">Study with clarity</p></div></div>;
}
