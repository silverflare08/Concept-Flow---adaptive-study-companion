import React from "react";
import { ArrowRight, CircleHelp, Download, FolderPlus, MessageSquarePlus, MessageSquareText } from "lucide-react";
import { SourceReferences } from "./StudyViews.jsx";

function Empty({ icon, title, body }) {
  return <div className="glass-card border-dashed p-8 text-center"><div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-lilac text-plum">{icon}</div><h2 className="mt-4 text-lg font-bold">{title}</h2><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-600">{body}</p></div>;
}

export default function TutorPage({ api, workspace, query, setQuery, askTutor, state, conversationId, newChat }) {
  if (!workspace.source_count) return <div className="space-y-6"><div><p className="eyebrow">Evidence-first tutoring</p><h1 className="mt-1 text-2xl font-extrabold">Ask about your course</h1><p className="mt-2 text-sm text-slate-600">Tutoring begins after you add any supported study material.</p></div><Empty icon={<FolderPlus size={24}/>} title="Your workspace is empty" body="Upload documents, images, handwriting, audio, video, or a supported link first."/></div>;
  return <div className="mx-auto max-w-4xl space-y-6">
    <div className="flex flex-wrap items-end justify-between gap-4"><div><p className="eyebrow">Evidence-first tutoring</p><h1 className="mt-1 text-2xl font-extrabold">Learn with your course material</h1><p className="mt-2 text-sm text-slate-600">Every conversation is saved inside {workspace.name}.</p></div><div className="flex gap-2"><button onClick={newChat} className="secondary-button"><MessageSquarePlus size={16}/> New chat</button>{conversationId && <a className="secondary-button" href={`${api}/api/conversations/${conversationId}/download`}><Download size={16}/> Download</a>}</div></div>
    <div className="glass-card p-3"><div className="flex flex-col gap-3 sm:flex-row"><div className="relative flex-1"><MessageSquareText className="absolute left-4 top-3.5 text-slate-400" size={19}/><input value={query} onChange={event => setQuery(event.target.value)} onKeyDown={event => event.key === "Enter" && askTutor()} className="w-full rounded-xl border border-slate-200 bg-white py-3 pl-11 pr-4 outline-none transition focus:border-plum" placeholder="For example: Teach this concept in simple words"/></div><button disabled={state.status === "loading"} onClick={askTutor} className="primary-button justify-center disabled:opacity-50">{state.status === "loading" ? "Teaching…" : "Ask tutor"}<ArrowRight size={17}/></button></div></div>
    {state.reply && state.status === "ready" && <section className="glass-card border-l-4 border-l-plum p-6"><p className="whitespace-pre-wrap text-lg leading-8 text-slate-700">{state.reply.answer}</p><h2 className="mb-3 mt-5 text-xs font-bold uppercase tracking-[.14em] text-slate-500">Verified course evidence</h2><SourceReferences evidence={state.reply.citations} api={api}/><div className="mt-5 rounded-2xl bg-lilac/50 p-4 text-sm text-slate-700"><b>Next step:</b> {state.reply.follow_up}</div></section>}
    {state.status === "empty" && <Empty icon={<CircleHelp size={24}/>} title="Not covered by your material" body={state.message}/>} 
    {state.status === "error" && <div className="rounded-2xl bg-peach p-5 text-sm text-slate-700"><b>Tutor unavailable:</b> {state.message}<p className="mt-2">Make sure Ollama is running and the local instruction model is installed.</p></div>}
  </div>;
}
