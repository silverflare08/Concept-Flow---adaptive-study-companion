import React, { useEffect, useState } from "react";
import { ArrowRight, BookOpenCheck, CircleHelp, FolderPlus, MessageSquarePlus, MessageSquareText, Sparkles, Square, Volume2 } from "lucide-react";
import { SourceReferences } from "./StudyViews.jsx";
import WorkingState from "./WorkingState.jsx";
import DownloadMenu from "./DownloadMenu.jsx";
import RichStudyText from "./RichStudyText.jsx";

function Empty({ icon, title, body }) {
  return <div className="glass-card border-dashed p-8 text-center"><div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-lilac text-plum">{icon}</div><h2 className="mt-4 text-lg font-bold">{title}</h2><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-600">{body}</p></div>;
}

export default function TutorPage({ api, workspace, query, setQuery, askTutor, state, conversationId, newChat, studyWholeMaterial, overviewProgress }) {
  const [selectedSources, setSelectedSources] = useState([]);
  const [speaking, setSpeaking] = useState(false);
  const [language, setLanguage] = useState("english");
  function toggleSource(id) { setSelectedSources(current => current.includes(id) ? current.filter(item => item !== id) : [...current, id]); }
  function toggleSpeech() {
    if (!("speechSynthesis" in window) || !state.reply?.answer) return;
    if (speaking) { window.speechSynthesis.cancel(); setSpeaking(false); return; }
    const utterance = new SpeechSynthesisUtterance(state.reply.answer.replace(/[#*_>`-]/g, " "));
    utterance.rate = 0.95;
    utterance.lang = language === "english" ? "en-IN" : "hi-IN";
    const matchingVoice = window.speechSynthesis.getVoices().find(voice => voice.lang.toLowerCase().startsWith(language === "english" ? "en-in" : "hi"));
    if (matchingVoice) utterance.voice = matchingVoice;
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    window.speechSynthesis.cancel(); window.speechSynthesis.speak(utterance); setSpeaking(true);
  }
  useEffect(() => () => { if ("speechSynthesis" in window) window.speechSynthesis.cancel(); }, []);
  if (!workspace.source_count) return <div className="space-y-6"><div><p className="eyebrow">Evidence-first tutoring</p><h1 className="mt-1 text-2xl font-extrabold">Ask about your course</h1><p className="mt-2 text-sm text-slate-600">Tutoring begins after you add any supported study material.</p></div><Empty icon={<FolderPlus size={24}/>} title="Your workspace is empty" body="Upload documents, images, handwriting, audio, video, or a supported link first."/></div>;
  return <div className="mx-auto max-w-4xl space-y-6">
    <div className="flex flex-wrap items-end justify-between gap-4"><div><p className="eyebrow">Evidence-first tutoring</p><h1 className="mt-1 text-2xl font-extrabold">Learn with your course material</h1><p className="mt-2 text-sm text-slate-600">Every conversation is saved inside {workspace.name}.</p></div><div className="flex gap-2"><button onClick={newChat} className="secondary-button"><MessageSquarePlus size={16}/> New chat</button>{conversationId && <DownloadMenu label="Download chat" href={`${api}/api/conversations/${conversationId}/download`}/>}</div></div>
    <LanguageChoice language={language} setLanguage={setLanguage}/>
    <section className="glass-card bg-gradient-to-r from-lilac/60 to-mint/40 p-5"><div className="flex items-start gap-3"><div className="rounded-xl bg-white p-2 text-plum shadow-sm"><BookOpenCheck size={20}/></div><div className="min-w-0 flex-1"><p className="flex items-center gap-2 font-bold">Study the complete material <Sparkles size={15} className="text-plum"/></p><p className="mt-1 text-sm leading-5 text-slate-600">Start a fresh saved lesson that explains the major ideas, definitions, processes, examples, exam points and self-check questions—in source order.</p><div className="mt-3 flex flex-wrap gap-2"><button onClick={() => setSelectedSources([])} className={`rounded-full px-3 py-1.5 text-xs font-bold ${selectedSources.length === 0 ? "bg-plum text-white" : "bg-white text-slate-600"}`}>All materials</button>{workspace.sources.map(source => <button key={source.id} onClick={() => toggleSource(source.id)} className={`max-w-full truncate rounded-full px-3 py-1.5 text-xs font-bold ${selectedSources.includes(source.id) ? "bg-mint text-emerald-800 ring-1 ring-emerald-300" : "bg-white text-slate-600"}`}>{source.name}</button>)}</div><button disabled={overviewProgress?.status === "running"} onClick={() => studyWholeMaterial(selectedSources, language)} className="primary-button mt-4 disabled:cursor-wait disabled:opacity-70"><Sparkles size={16}/>{overviewProgress?.status === "running" ? "Building complete lesson…" : "Summarize and teach everything"}</button></div></div></section>
    {overviewProgress?.status === "running" && <WorkingState title="Preparing your complete exam lesson" detail={overviewProgress.total_batches ? `${overviewProgress.completed_batches} of ${overviewProgress.total_batches} sections taught. ConceptFlow is following the material in order and retaining verified citations.` : "Organising the selected material into teachable sections. This continues in the background."} progress={overviewProgress.total_batches ? overviewProgress.completed_batches / overviewProgress.total_batches * 100 : null}/>}
    {overviewProgress?.status === "complete" && overviewProgress.result?.generation_mode === "extractive_fallback" && <div className="rounded-2xl bg-peach p-4 text-sm leading-6 text-slate-700"><b>Your cited lesson was still created.</b> Ollama or the configured model was unavailable, so this version uses readable source excerpts. Start Ollama and generate again when you want an AI-written explanation.</div>}
    <div className="glass-card p-3"><div className="flex flex-col gap-3 sm:flex-row"><div className="relative flex-1"><MessageSquareText className="absolute left-4 top-3.5 text-slate-400" size={19}/><input value={query} onChange={event => setQuery(event.target.value)} onKeyDown={event => event.key === "Enter" && askTutor(language)} className="w-full rounded-xl border border-slate-200 bg-white py-3 pl-11 pr-4 outline-none transition focus:border-plum" placeholder="For example: Teach this concept in simple words"/></div><button disabled={state.status === "loading"} onClick={() => askTutor(language)} className="primary-button justify-center disabled:opacity-50">{state.status === "loading" ? "Teaching…" : "Ask tutor"}<ArrowRight size={17}/></button></div></div>
    {state.reply && state.status === "ready" && <section className="glass-card border-l-4 border-l-plum p-6"><div className="mb-4 flex justify-end"><button onClick={toggleSpeech} className="secondary-button">{speaking ? <Square size={16}/> : <Volume2 size={17}/>} {speaking ? "Stop audio" : "Listen to explanation"}</button></div><RichStudyText text={state.reply.answer}/><h2 className="mb-3 mt-5 text-xs font-bold uppercase tracking-[.14em] text-slate-500">Verified course evidence</h2><SourceReferences evidence={state.reply.citations} api={api}/><div className="mt-5 rounded-2xl bg-lilac/50 p-4 text-sm text-slate-700"><b>Next step:</b> {state.reply.follow_up}</div></section>}
    {state.status === "empty" && <Empty icon={<CircleHelp size={24}/>} title="Not covered by your material" body={state.message}/>} 
    {state.status === "error" && <div className="rounded-2xl bg-peach p-5 text-sm text-slate-700"><b>Could not complete this request:</b> {state.message}</div>}
  </div>;
}

function LanguageChoice({ language, setLanguage }) {
  const choices = [["english", "English"], ["hindi", "हिंदी"], ["hinglish", "Hinglish"]];
  return <section className="glass-card flex flex-wrap items-center justify-between gap-3 p-4"><div><p className="text-sm font-bold">Explanation language</p><p className="text-xs text-slate-500">Change this before asking or creating a complete lesson.</p></div><div className="flex rounded-xl bg-slate-100 p-1">{choices.map(([value, label]) => <button key={value} onClick={() => setLanguage(value)} className={`rounded-lg px-3 py-2 text-xs font-bold ${language === value ? "bg-white text-plum shadow-sm" : "text-slate-500"}`}>{label}</button>)}</div></section>;
}
