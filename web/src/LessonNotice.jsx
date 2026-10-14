import React from "react";

export default function LessonNotice({ lesson }) {
  if (lesson?.generation_mode !== "extractive_fallback") return null;
  const reasons = [...new Set((lesson.fallback_reasons || []).map(item => item.message).filter(Boolean))];
  const locations = [...new Set((lesson.fallback_reasons || []).flatMap(item => item.locations || []))];
  const unavailable = reasons.some(reason => /unavailable|not currently available|start ollama|missing model/i.test(reason));
  return <div role="status" className="rounded-2xl bg-peach p-4 text-sm leading-6 text-slate-700">
    <p className="font-semibold">Some source passages need review.</p>
    {lesson.requested_language && lesson.requested_language !== "english" && <p className="mt-1 font-medium">The requested {lesson.requested_language === "hinglish" ? "Romanised Hinglish" : "Hindi"} lesson was not completed for every section. Excerpts below retain their source language; they are not a translation.</p>}
    <p>Usable passages are still explained when possible. Flagged excerpts are not verified lessons.</p>
    {reasons.length > 0 && <ul className="mt-2 list-disc space-y-1 pl-5">{reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>}
    {locations.length > 0 && <p className="mt-2 text-xs">Affected locations: {locations.join(" · ")}</p>}
    <p className="mt-2">{unavailable ? "Open Ollama and check the configured model, then generate again." : "Check the flagged original pages. Re-upload them to use the improved reader; changing font or restarting Ollama cannot repair wrongly read symbols."}</p>
  </div>;
}
