import React, { useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, BookOpen, Layers3, RotateCcw, Shuffle } from "lucide-react";
import DownloadMenu from "./DownloadMenu.jsx";
import { SourceReferences } from "./StudyViews.jsx";

export default function FlashcardsPage({ api, workspace, guide, setPage, generate, progress }) {
  const cards = useMemo(() => guide?.concepts || [], [guide]);
  const [order, setOrder] = useState([]);
  const [position, setPosition] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [selectedSources, setSelectedSources] = useState([]);
  const [error, setError] = useState("");
  useEffect(() => { setOrder(cards.map((_, index) => index)); setPosition(0); setRevealed(false); }, [cards]);
  // A saved guide can arrive before the effect has populated `order`.
  // Falling back to the natural first-card index prevents an undefined-card
  // render (the former cause of the blank white Flashcards page).
  const cardIndex = order[position] ?? position ?? 0;
  const card = cards[cardIndex] || cards[0];

  function move(amount) {
    if (!order.length) return;
    setPosition(current => (current + amount + order.length) % order.length);
    setRevealed(false);
  }
  function shuffle() {
    setOrder(current => [...current].sort(() => Math.random() - 0.5));
    setPosition(0); setRevealed(false);
  }

  async function buildCards() {
    setError("");
    try { await generate("flashcards", selectedSources); }
    catch (issue) { setError(issue.message); }
  }

  if (!workspace.source_count) return <Empty title="Add material before creating flashcards" body="Flashcards stay grounded in the material inside your active workspace." action={() => setPage("Materials")} actionLabel="Open materials"/>;
  if (!cards.length) return <div className="space-y-5"><header><p className="eyebrow">Active recall</p><h1 className="mt-1 text-2xl font-extrabold">Generate source-grounded flashcards</h1><p className="mt-2 text-sm text-slate-600">Choose one material, several materials, or the complete workspace.</p></header><section className="glass-card p-6"><div className="flex flex-wrap gap-2"><button onClick={() => setSelectedSources([])} className={`rounded-full px-3 py-2 text-xs font-bold ${selectedSources.length === 0 ? "bg-plum text-white" : "bg-slate-100 text-slate-600"}`}>All materials</button>{workspace.sources.map(source => <button key={source.id} onClick={() => setSelectedSources(current => current.includes(source.id) ? current.filter(id => id !== source.id) : [...current, source.id])} className={`max-w-full truncate rounded-full px-3 py-2 text-xs font-bold ${selectedSources.includes(source.id) ? "bg-mint text-emerald-800 ring-1 ring-emerald-300" : "bg-slate-100 text-slate-600"}`}>{source.name}</button>)}</div><button disabled={progress?.status === "running"} onClick={buildCards} className="primary-button mt-5 disabled:opacity-60">{progress?.status === "running" ? "Building flashcards…" : "Generate flashcards"}<ArrowRight size={16}/></button>{error && <p className="mt-4 rounded-xl bg-peach p-3 text-sm text-slate-700">{error}</p>}</section></div>;

  if (!card) return <Empty title="Your flashcards are being prepared" body="Open Learning Flow once, then return here to practise the generated concepts." action={() => setPage("Learning Flow")} actionLabel="Open Learning Flow"/>;

  return <div className="mx-auto max-w-4xl space-y-5">
    <header className="flex flex-wrap items-end justify-between gap-4"><div><p className="eyebrow">Active recall</p><h1 className="mt-1 text-2xl font-extrabold">Source-grounded flashcards</h1><p className="mt-2 text-sm text-slate-600">Try to answer aloud, reveal the explanation, then open the exact source when needed.</p></div><DownloadMenu label="Download flashcards" href={`${api}/api/flashcards/download`}/></header>
    <div className="flex items-center justify-between text-sm text-slate-500"><span>Card {position + 1} of {cards.length}</span><button onClick={shuffle} className="secondary-button"><Shuffle size={16}/>Shuffle</button></div>
    <button onClick={() => setRevealed(value => !value)} className="glass-card block min-h-72 w-full p-7 text-left transition hover:-translate-y-0.5 hover:shadow-lg" aria-live="polite">
      <p className="eyebrow">{revealed ? "Answer" : card.topic}</p>
      {!revealed ? <div className="grid min-h-48 place-items-center text-center"><div><Layers3 className="mx-auto text-plum" size={28}/><h2 className="mt-4 text-2xl font-extrabold">Explain: {card.name}</h2><p className="mt-3 text-sm text-slate-500">Think first, then click to reveal.</p></div></div> : <div className="mt-4"><h2 className="text-xl font-bold">{card.name}</h2><p className="mt-3 text-sm leading-7 text-slate-700">{card.description}</p>{card.key_points?.length > 0 && <ul className="mt-4 list-disc space-y-2 pl-5 text-sm text-slate-600">{card.key_points.map((point, index) => <li key={index}>{point}</li>)}</ul>}<div className="mt-5 border-t border-slate-100 pt-4"><SourceReferences evidence={card.evidence} api={api} compact/></div></div>}
    </button>
    <div className="flex items-center justify-center gap-3"><button onClick={() => move(-1)} className="secondary-button"><ArrowLeft size={16}/>Previous</button><button onClick={() => setRevealed(value => !value)} className="primary-button"><RotateCcw size={16}/>{revealed ? "Question" : "Reveal"}</button><button onClick={() => move(1)} className="secondary-button">Next<ArrowRight size={16}/></button></div>
  </div>;
}

function Empty({ title, body, action, actionLabel }) {
  return <div className="glass-card p-8 text-center"><BookOpen className="mx-auto text-plum" size={30}/><h1 className="mt-4 text-xl font-bold">{title}</h1><p className="mx-auto mt-2 max-w-lg text-sm text-slate-600">{body}</p><button onClick={action} className="primary-button mt-5">{actionLabel}<ArrowRight size={16}/></button></div>;
}
