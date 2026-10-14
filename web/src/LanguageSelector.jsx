import React from "react";
import { LANGUAGE_CHOICES, EXPERIMENTAL_LANGUAGE_NOTICE } from "./languageChoices.js";
export default function LanguageSelector({ value, onChange, label = "Language", className = "glass-card p-4" }) {
  return <section className={className}><label className="flex flex-wrap items-center gap-3 text-sm font-semibold"><span>{label}</span><select value={value} onChange={event => onChange(event.target.value)} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700">{LANGUAGE_CHOICES.map(([id, text]) => <option key={id} value={id}>{text}</option>)}</select></label><p className="mt-2 text-xs leading-5 text-slate-500">{value === "english" ? "English is the default. Additional languages are experimental." : EXPERIMENTAL_LANGUAGE_NOTICE}</p></section>;
}
