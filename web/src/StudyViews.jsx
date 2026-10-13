import React, { useState } from "react";
import { ArrowRight, BookOpen, FileText, GitBranch, RefreshCw } from "lucide-react";
import WorkingState from "./WorkingState.jsx";

export function SourceReferences({ evidence = [], api = "", compact = false }) {
  return <div className="space-y-2">{evidence.map((source, index) => {
    const seconds = Math.floor(source.start_seconds || 0); const timestamp = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
    const location = source.page ? `PDF page ${source.page}` : source.slide ? `Slide ${source.slide}` : source.start_seconds != null ? `Timestamp ${timestamp}` : source.section || source.label;
    const href = source.target_uri?.startsWith("/") ? `${api}${source.target_uri}` : source.target_uri;
    const openLabel = source.page ? `Open PDF at page ${source.page}` : source.slide ? `Download slides · go to slide ${source.slide}` : source.start_seconds != null ? `Open at ${timestamp}` : "Open original source";
    return <div key={`${source.label}-${index}`} className="rounded-xl bg-sky/35 p-3 text-sm">
      <p className="flex items-start gap-2 font-semibold text-slate-700"><FileText size={16} className="mt-0.5 shrink-0"/><span>{location}{source.source_name ? ` in ${source.source_name}` : ""}</span></p>
      {!compact && source.excerpt && <blockquote className="mt-2 leading-6 text-slate-600">“{source.excerpt}”</blockquote>}
      {href && <a href={href} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 font-semibold text-plum underline underline-offset-4">{openLabel}<ArrowRight size={14}/></a>}
    </div>;
  })}</div>;
}

export default function StudyViews({ mode, workspace, guide, generate, progress, startTutorFor, setPage, api }) {
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState(true);
  const [selectedId, setSelectedId] = useState(null);
  const [selectedSources, setSelectedSources] = useState([]);
  const mindMap = mode === "revision";
  const anyGenerationRunning = progress?.status === "running";
  const busy = anyGenerationRunning && progress?.view === mode;
  const concepts = guide?.concepts || [];
  const byId = Object.fromEntries(concepts.map(concept => [concept.concept_id, concept]));
  const revisionOrder = (guide?.revision_concepts || concepts).map(concept => byId[concept.concept_id]).filter(Boolean);
  const groups = {};
  revisionOrder.forEach(concept => { (groups[concept.topic] ||= []).push(concept); });
  const selected = byId[selectedId];
  const featureName = mindMap ? "Revision Mind Map" : "Learning Flow";
  function toggleSource(sourceId) {
    setSelectedSources(current => current.includes(sourceId) ? current.filter(id => id !== sourceId) : [...current, sourceId]);
  }
  async function createGuide() { setError(""); try { await generate(mode, selectedSources); } catch (issue) { setError(issue.message); } }
  return <div className="space-y-6">
    <div><p className="eyebrow">{mindMap ? "Last-minute revision" : "Your study starting point"}</p><h1 className="mt-1 text-2xl font-extrabold">{mindMap ? "Revision Mind Map" : "Learning Flow"}</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{mindMap ? "See your selected material as topics, concepts and key revision points. Follow the branches to refresh your understanding before an exam." : "Follow a suggested study order. Each step tells you what the topic means, how to study it and exactly where to start reading."}</p></div>
    <div className="flex flex-wrap gap-3" aria-label="Study view"><button onClick={() => setPage("Learning Flow")} className={mindMap ? "secondary-button" : "primary-button"}><BookOpen size={17}/>Learning Flow</button><button onClick={() => setPage("Revision Mind Map")} className={mindMap ? "primary-button" : "secondary-button"}><GitBranch size={17}/>Revision Mind Map</button></div>
    {!workspace.chunk_count ? <div className="glass-card p-8"><h2 className="text-xl font-bold">Add readable study material first</h2><p className="mt-2 text-slate-600">Upload a PDF or slide deck in Materials to create these study views.</p><button onClick={() => setPage("Materials")} className="primary-button mt-5">Add material<ArrowRight size={16}/></button></div> : <>
      <section className="glass-card p-5"><div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between"><div className="min-w-0 flex-1"><p className="font-semibold">Choose material for this {mindMap ? "map" : "flow"}</p><p className="mt-1 text-xs text-slate-500">Use the whole workspace, one source, or any combination.</p><div className="mt-3 flex flex-wrap gap-2"><button onClick={() => setSelectedSources([])} className={`rounded-full px-3 py-1.5 text-xs font-bold ${selectedSources.length === 0 ? "bg-plum text-white" : "bg-slate-100 text-slate-600"}`}>All materials</button>{workspace.sources.map(source => <button key={source.id} onClick={() => toggleSource(source.id)} className={`max-w-full truncate rounded-full px-3 py-1.5 text-xs font-bold ${selectedSources.includes(source.id) ? "bg-mint text-emerald-800 ring-1 ring-emerald-300" : "bg-slate-100 text-slate-600"}`}>{source.name}</button>)}</div>{guide && <p className="mt-3 text-xs text-slate-500">Currently shown: {guide.selected_source_names?.length ? guide.selected_source_names.join(", ") : "all workspace materials"}.</p>}</div><button disabled={anyGenerationRunning} onClick={createGuide} className="primary-button shrink-0 disabled:cursor-wait disabled:opacity-90"><RefreshCw className={busy ? "animate-spin" : ""} size={16}/>{busy ? `Building ${featureName}…` : guide ? `Regenerate ${featureName}` : `Generate ${featureName}`}</button></div></section>
      {busy && <WorkingState title={`Building your ${featureName}`} detail={progress.total_batches ? `${progress.completed_batches} of ${progress.total_batches} model sections processed. The local model is extracting concepts, ordering prerequisites and attaching citations.` : progress.analysis_chunks && progress.source_chunks > progress.analysis_chunks ? `Optimised ${progress.source_chunks} timestamp chunks into ${progress.analysis_chunks} citation-preserving analysis blocks. Starting the local model now.` : "Preparing the selected material and starting the local AI model."} progress={progress.total_batches ? (progress.completed_batches / progress.total_batches) * 100 : null}/>}
      {(error || (progress?.status === "failed" && progress?.view === mode)) && <div role="alert" className="rounded-2xl bg-peach p-4 text-sm text-slate-700">{error || progress.error}</div>}
      {guide && <><p className="text-sm text-slate-500">{guide.coverage?.mapped_chunks} of {guide.coverage?.indexed_chunks} indexed text chunks represented. Generated summaries may still need checking against the cited pages. Scanned text and diagrams are not yet included.</p>
        {mindMap ? <>
          <div className="flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-slate-600">Material → topic → concept → revision points</p><button className="secondary-button" onClick={() => setExpanded(value => !value)}>{expanded ? "Compact overview" : "Show revision points"}</button></div>
          <section aria-label="Revision mind map" className="glass-card p-5 sm:p-7">
            <div className="mx-auto max-w-lg rounded-2xl bg-plum p-5 text-center text-white"><p className="text-xs font-semibold uppercase tracking-widest">Your material</p><h2 className="mt-2 break-words text-xl font-bold">{guide.title}</h2></div>
            <div className="mx-auto h-8 w-px bg-lavender"/>
            <div className="grid gap-7 md:grid-cols-2 xl:grid-cols-3">{Object.entries(groups).map(([topic, items]) => <section key={topic} className="min-w-0 border-t-2 border-lavender pt-4"><h3 className="rounded-xl bg-mint p-3 text-center font-bold text-slate-700">{topic}</h3><div className="ml-3 mt-4 space-y-4 border-l-2 border-lavender pl-4">{items.map(concept => <article key={concept.concept_id} className="relative min-w-0 before:absolute before:-left-[18px] before:top-5 before:w-4 before:border-t-2 before:border-lavender"><button aria-pressed={selectedId === concept.concept_id} onClick={() => setSelectedId(concept.concept_id)} className={`w-full break-words rounded-xl p-3 text-left font-semibold transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-plum ${selectedId === concept.concept_id ? "bg-lilac text-plum" : "bg-slate-50 text-slate-700 hover:bg-lilac/50"}`}>{concept.name}</button>{expanded && <ul className="mt-2 space-y-2 pl-4 text-sm leading-6 text-slate-600">{(concept.key_points || []).map((point, index) => <li key={index} className="list-disc break-words">{point}</li>)}</ul>}<p className="mt-2 break-words text-xs leading-5 text-plum">{concept.evidence?.map(source => `${source.source_name} · ${source.page ? `PDF page ${source.page}` : `Slide ${source.slide}`}`).join("; ")}</p></article>)}</div></section>)}</div>
          </section>
          {selected && <section className="glass-card p-6" aria-live="polite"><h2 className="text-xl font-bold">{selected.name}</h2><p className="my-3 leading-7 text-slate-600">{selected.description}</p><SourceReferences evidence={selected.evidence} api={api}/><button onClick={() => startTutorFor(selected.name)} className="primary-button mt-4">Explain this to me<ArrowRight size={16}/></button></section>}
        </> : <>
          <div className="glass-card bg-mint/50 p-5"><p className="eyebrow">Start here</p><h2 className="mt-2 text-xl font-bold">1. {concepts[0]?.name}</h2><p className="mt-2 text-sm leading-6 text-slate-600">Read the first cited location below, then follow the study steps. The order respects extracted prerequisites and keeps document order for topics without known dependencies.</p></div>
          <ol className="space-y-5">{concepts.map((concept, index) => <li key={concept.concept_id} className="glass-card p-5 sm:p-6"><div className="flex items-start gap-4"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-plum font-bold text-white">{index + 1}</span><div className="min-w-0 flex-1"><p className="eyebrow">{concept.topic}</p><h2 className="mt-1 text-xl font-bold">{concept.name}</h2><p className="mt-3 leading-7 text-slate-600">{concept.description}</p><p className="mt-3 text-sm text-slate-600"><strong>Study before this:</strong> {concept.prerequisite_ids?.length ? concept.prerequisite_ids.map(id => byId[id]?.name).filter(Boolean).join(", ") : "No prerequisite identified in your material."}</p><h3 className="mt-5 font-semibold">How to study this topic</h3><ol className="mt-2 list-decimal space-y-2 pl-5 text-sm leading-6 text-slate-600">{concept.study_steps?.map((step, number) => <li key={number}>{step}</li>)}</ol><h3 className="mb-3 mt-5 font-semibold">Start reading here</h3><SourceReferences evidence={concept.evidence} api={api}/><button onClick={() => startTutorFor(concept.name)} className="secondary-button mt-4">Teach me this topic<ArrowRight size={16}/></button></div></div></li>)}</ol>
        </>}
      </>}
    </>}
  </div>;
}
