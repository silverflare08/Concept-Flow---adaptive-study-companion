import React, { useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, Headphones, Play, Sparkles, Square, Video, Volume2 } from "lucide-react";
import { SourceReferences } from "./StudyViews.jsx";
import WorkingState from "./WorkingState.jsx";

function cleanSpeech(text) {
  return text.replace(/[#*_>`]/g, " ").replace(/\s+/g, " ").trim();
}

function lessonSlides(answer) {
  const sections = answer.split(/\n---\n|(?=\n##\s)/).map(item => item.trim()).filter(Boolean);
  return sections.flatMap((section, sectionIndex) => {
    const title = section.match(/^#{1,3}\s+(.+)$/m)?.[1] || `Lesson section ${sectionIndex + 1}`;
    const body = section.replace(/^#{1,3}\s+.+$/m, "").trim();
    if (body.length <= 1500) return [{ title, body }];
    return (body.match(/[\s\S]{1,1400}(?:\s|$)/g) || [body]).map((part, index) => ({ title: `${title} · ${index + 1}`, body: part.trim() }));
  });
}

export default function StudyMediaPage({ api, workspace, requestedSourceId, requestedMode = "audio", refreshLibrary }) {
  const [sourceId, setSourceId] = useState(requestedSourceId || workspace.sources[0]?.id || "");
  const [mode, setMode] = useState(requestedMode);
  const [job, setJob] = useState(null);
  const [lesson, setLesson] = useState(null);
  const [error, setError] = useState("");
  const [slide, setSlide] = useState(0);
  const [playing, setPlaying] = useState(false);
  const slides = useMemo(() => lesson ? lessonSlides(lesson.answer) : [], [lesson]);

  useEffect(() => {
    const validRequest = workspace.sources.some(source => source.id === requestedSourceId);
    setSourceId(validRequest ? requestedSourceId : workspace.sources[0]?.id || "");
    setMode(requestedMode); setLesson(null); setJob(null); setError(""); setSlide(0); stopSpeech();
  }, [workspace.id, workspace.source_count, requestedSourceId, requestedMode]);
  useEffect(() => () => { if ("speechSynthesis" in window) window.speechSynthesis.cancel(); }, []);

  async function generateLesson() {
    if (!sourceId) { setError("Choose one material first."); return; }
    setError(""); setLesson(null); setSlide(0); setPlaying(false);
    try {
      const response = await fetch(`${api}/api/tutor/overview`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source_ids: [sourceId] }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not start this explanation.");
      let current = data.job; setJob(current);
      while (current?.status === "running") {
        await new Promise(resolve => setTimeout(resolve, 1500));
        const statusResponse = await fetch(`${api}/api/tutor/overview/status?job_id=${encodeURIComponent(data.job.job_id)}`);
        const status = await statusResponse.json();
        if (!statusResponse.ok || !status.job) throw new Error("Could not read explanation progress.");
        current = status.job; setJob(current);
      }
      if (current?.status !== "complete") throw new Error(current?.error || "The explanation could not be completed.");
      setLesson(current.result); await refreshLibrary();
    } catch (issue) { setError(issue.message); setJob(current => ({ ...current, status: "failed" })); }
  }

  function stopSpeech() { if ("speechSynthesis" in window) window.speechSynthesis.cancel(); setPlaying(false); }
  function speak(text, onend) {
    if (!("speechSynthesis" in window)) { setError("This browser does not provide speech playback."); return; }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(cleanSpeech(text)); utterance.rate = 0.94;
    utterance.onend = () => onend?.(); utterance.onerror = () => setPlaying(false);
    window.speechSynthesis.speak(utterance); setPlaying(true);
  }
  function playAudio() { speak(lesson.answer, () => setPlaying(false)); }
  function playSlides(from = slide) {
    if (!slides.length) return;
    setSlide(from); setPlaying(true);
    speak(`${slides[from].title}. ${slides[from].body}`, () => {
      if (from + 1 < slides.length) playSlides(from + 1); else setPlaying(false);
    });
  }

  if (!workspace.sources.length) return <div className="glass-card p-8 text-center"><h1 className="text-xl font-bold">Add material to create an explanation</h1><p className="mt-2 text-sm text-slate-600">Audio and narrated slides are always generated from one selected source.</p></div>;
  const selectedName = workspace.sources.find(source => source.id === sourceId)?.name;
  return <div className="space-y-5"><header><p className="eyebrow">Study media</p><h1 className="mt-1 text-2xl font-extrabold">Audio and narrated explanations</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">Choose a material. ConceptFlow creates a cited lesson, then your browser narrates it for free. Video mode presents the lesson as automatically narrated slides.</p></header>
    <section className="glass-card p-5"><div className="grid gap-4 md:grid-cols-[1fr_auto]"><div><label className="text-sm font-bold">Material</label><select value={sourceId} onChange={event => setSourceId(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm">{workspace.sources.map(source => <option key={source.id} value={source.id}>{source.name}</option>)}</select></div><div><p className="text-sm font-bold">Explanation format</p><div className="mt-2 flex gap-2"><button onClick={() => setMode("audio")} className={mode === "audio" ? "primary-button" : "secondary-button"}><Headphones size={16}/>Audio</button><button onClick={() => setMode("video")} className={mode === "video" ? "primary-button" : "secondary-button"}><Video size={16}/>Narrated slides</button></div></div></div><button disabled={job?.status === "running"} onClick={generateLesson} className="primary-button mt-5 disabled:opacity-60"><Sparkles size={16}/>{job?.status === "running" ? "Preparing explanation…" : `Create ${mode === "audio" ? "audio" : "video-style"} lesson`}</button></section>
    {job?.status === "running" && <WorkingState title={`Preparing ${selectedName}`} detail={job.total_batches ? `${job.completed_batches} of ${job.total_batches} cited lesson sections completed.` : "Organising the selected material into a teachable sequence."} progress={job.total_batches ? job.completed_batches / job.total_batches * 100 : null}/>}
    {error && <div className="rounded-2xl bg-peach p-4 text-sm text-slate-700">{error}</div>}
    {lesson && mode === "audio" && <section className="glass-card p-6"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="eyebrow">Audio lesson</p><h2 className="mt-1 text-xl font-bold">{selectedName}</h2></div><button onClick={playing ? stopSpeech : playAudio} className="primary-button">{playing ? <Square size={16}/> : <Volume2 size={17}/>} {playing ? "Stop" : "Play explanation"}</button></div><p className="mt-5 max-h-96 overflow-y-auto whitespace-pre-wrap text-sm leading-7 text-slate-700">{lesson.answer}</p></section>}
    {lesson && mode === "video" && slides.length > 0 && <section className="space-y-4"><div className="aspect-video overflow-hidden rounded-3xl bg-gradient-to-br from-[#574681] via-[#7665a7] to-[#9bc9b8] p-5 shadow-xl sm:p-10"><div className="flex h-full flex-col rounded-2xl bg-white/95 p-6 sm:p-9"><div className="flex items-center justify-between"><span className="rounded-full bg-lilac px-3 py-1 text-xs font-bold text-plum">{slide + 1} / {slides.length}</span><span className="text-xs font-semibold text-slate-400">{selectedName}</span></div><div className="my-auto"><h2 className="text-xl font-extrabold text-slate-800 sm:text-3xl">{slides[slide].title}</h2><p className="mt-4 max-h-48 overflow-y-auto whitespace-pre-wrap text-xs leading-6 text-slate-600 sm:text-sm">{slides[slide].body}</p></div><div className="h-1.5 overflow-hidden rounded-full bg-slate-100"><div className="h-full bg-plum transition-all" style={{ width: `${(slide + 1) / slides.length * 100}%` }}/></div></div></div><div className="flex flex-wrap items-center justify-center gap-2"><button disabled={slide === 0} onClick={() => { stopSpeech(); setSlide(value => value - 1); }} className="secondary-button disabled:opacity-40"><ArrowLeft size={16}/>Previous</button><button onClick={playing ? stopSpeech : () => playSlides(slide)} className="primary-button">{playing ? <Square size={16}/> : <Play size={16}/>} {playing ? "Stop narration" : "Play narrated lesson"}</button><button disabled={slide === slides.length - 1} onClick={() => { stopSpeech(); setSlide(value => value + 1); }} className="secondary-button disabled:opacity-40">Next<ArrowRight size={16}/></button></div></section>}
    {lesson?.generation_mode === "extractive_fallback" && <div className="rounded-2xl bg-peach p-4 text-sm text-slate-700">Ollama was unavailable, so this media lesson uses cited source excerpts. It remains grounded, but an Ollama-generated version will provide smoother explanations.</div>}
    {lesson?.citations?.length > 0 && <section className="glass-card p-5"><h2 className="font-bold">Lesson sources</h2><div className="mt-3"><SourceReferences evidence={lesson.citations} api={api} compact/></div></section>}
  </div>;
}
