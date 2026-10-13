import React, { useEffect, useMemo, useState } from "react";
import { ArrowRight, CheckCircle2, Download, FileQuestion, RefreshCw, Sparkles, Target, XCircle } from "lucide-react";
import { SourceReferences } from "./StudyViews.jsx";
import WorkingState from "./WorkingState.jsx";
import DownloadMenu from "./DownloadMenu.jsx";

const TYPES = [
  ["mcq", "Multiple choice"],
  ["short_answer", "Short answer"],
  ["numerical", "Numerical"],
  ["true_false", "True / false"],
  ["fill_blank", "Fill in the blank"],
];

export default function AssessmentPage({ api, workspace, guide, refreshLibrary }) {
  const topics = useMemo(() => Array.from(new Set(guide?.concepts?.map(item => item.topic).filter(Boolean) || [])), [guide]);
  const [scope, setScope] = useState([]);
  const [count, setCount] = useState(5);
  const [difficulty, setDifficulty] = useState("medium");
  const [types, setTypes] = useState(["mcq", "short_answer"]);
  const [assessment, setAssessment] = useState(null);
  const [answers, setAnswers] = useState({});
  const [report, setReport] = useState(null);
  const [mastery, setMastery] = useState([]);
  const [recent, setRecent] = useState([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [builderMode, setBuilderMode] = useState("quick");
  const [assessmentLanguage, setAssessmentLanguage] = useState("english");

  async function refreshAssessments() {
    const response = await fetch(`${api}/api/assessments`);
    if (response.ok) { const data = await response.json(); setRecent(data.assessments); setMastery(data.mastery); }
  }
  useEffect(() => { refreshAssessments(); }, [workspace.id]);

  function toggleType(value) {
    setTypes(current => current.includes(value) ? current.filter(item => item !== value) : [...current, value]);
  }
  function toggleTopic(value) {
    setScope(current => current.includes(value) ? current.filter(item => item !== value) : [...current, value]);
  }
  async function generate(preset = null) {
    const config = { ...(preset || { scope, question_count: count, difficulty, question_types: types }), language: assessmentLanguage };
    if (!config.question_types.length) { setError("Select at least one question type."); return; }
    setBusy("generate"); setError(""); setReport(null);
    try {
      const response = await fetch(`${api}/api/assessments`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(config) });
      const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Could not generate the assessment.");
      setAssessment(data); setAnswers({}); await refreshAssessments(); await refreshLibrary();
    } catch (error) { setError(error.message); } finally { setBusy(""); }
  }
  async function submit() {
    setBusy("submit"); setError("");
    try {
      const response = await fetch(`${api}/api/assessments/${assessment.id}/submit`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ answers }) });
      const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Could not grade this assessment.");
      setReport(data.report); setMastery(data.mastery); await refreshAssessments(); await refreshLibrary();
    } catch (error) { setError(error.message); } finally { setBusy(""); }
  }
  async function openAssessment(id) {
    setBusy("open"); setError("");
    try {
      const response = await fetch(`${api}/api/assessments/${id}`); const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not open the assessment.");
      setAssessment(data); setReport(data.report); setAnswers(Object.fromEntries((data.answers || []).map(item => [item.question_id, item.response])));
    } catch (error) { setError(error.message); } finally { setBusy(""); }
  }
  function reset() { setAssessment(null); setReport(null); setAnswers({}); setError(""); }

  if (!workspace.source_count) return <div className="space-y-6"><header><p className="eyebrow">Adaptive assessment</p><h1 className="mt-1 text-2xl font-extrabold">Practise from your own material</h1></header><div className="glass-card border-dashed p-8 text-center"><FileQuestion className="mx-auto text-plum" size={30}/><h2 className="mt-3 text-lg font-bold">Add study material first</h2><p className="mt-2 text-sm text-slate-500">Questions are generated only from evidence in the active course.</p></div></div>;

  if (!assessment) return <div className="space-y-5"><header><p className="eyebrow">Adaptive assessment</p><h1 className="mt-1 text-2xl font-extrabold">Build a source-grounded quiz</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">Start instantly with a prepared format, or customise every setting yourself. Questions are generated and verified from your material when you begin.</p></header>
    <div className="flex gap-2 rounded-2xl bg-white/70 p-2"><button onClick={() => setBuilderMode("quick")} className={builderMode === "quick" ? "primary-button" : "secondary-button"}>Quick tests</button><button onClick={() => setBuilderMode("custom")} className={builderMode === "custom" ? "primary-button" : "secondary-button"}>Custom test</button></div>
    <section className="glass-card flex flex-wrap items-center justify-between gap-3 p-4"><div><p className="text-sm font-bold">Question and solution language</p><p className="text-xs text-slate-500">The test and its worked feedback will use this language.</p></div><div className="flex rounded-xl bg-slate-100 p-1">{[["english", "English"], ["hindi", "हिंदी"], ["hinglish", "Hinglish"]].map(([value, label]) => <button key={value} onClick={() => setAssessmentLanguage(value)} className={`rounded-lg px-3 py-2 text-xs font-bold ${assessmentLanguage === value ? "bg-white text-plum shadow-sm" : "text-slate-500"}`}>{label}</button>)}</div></section>
    {builderMode === "quick" ? <section className="grid gap-4 md:grid-cols-3"><QuickTest title="Five-minute quiz" detail="5 medium MCQ and true/false questions." onClick={() => generate({ scope: [], question_count: 5, difficulty: "medium", question_types: ["mcq", "true_false"] })}/><QuickTest title="Mixed practice" detail="8 questions across objective and written formats." onClick={() => generate({ scope: [], question_count: 8, difficulty: "medium", question_types: ["mcq", "short_answer", "fill_blank"] })}/><QuickTest title="Challenge test" detail="10 difficult mixed questions from the whole workspace." onClick={() => generate({ scope: [], question_count: 10, difficulty: "hard", question_types: ["mcq", "short_answer", "numerical"] })}/></section> : <div className="grid gap-6 lg:grid-cols-[1.2fr_.8fr]"><section className="glass-card p-5"><label className="text-sm font-bold">Number of questions: {count}</label><input className="mt-3 w-full accent-[#7564a8]" type="range" min="1" max="12" value={count} onChange={event => setCount(Number(event.target.value))}/><h2 className="mt-5 text-sm font-bold">Difficulty</h2><div className="mt-3 flex flex-wrap gap-2">{["easy", "medium", "hard"].map(item => <button key={item} onClick={() => setDifficulty(item)} className={`rounded-full px-4 py-2 text-sm font-semibold capitalize ${difficulty === item ? "bg-plum text-white" : "bg-slate-100 text-slate-600"}`}>{item}</button>)}</div><h2 className="mt-5 text-sm font-bold">Question types</h2><div className="mt-3 grid gap-2 sm:grid-cols-3">{TYPES.map(([value, label]) => <button key={value} onClick={() => toggleType(value)} className={`rounded-xl border p-3 text-left text-sm font-semibold ${types.includes(value) ? "border-plum bg-lilac/60 text-plum" : "border-slate-100 bg-slate-50 text-slate-600"}`}>{label}</button>)}</div><h2 className="mt-5 text-sm font-bold">Topic scope</h2><p className="mt-1 text-xs text-slate-500">Leave everything unselected to use the whole course.</p><div className="mt-3 flex flex-wrap gap-2">{topics.length ? topics.map(topic => <button key={topic} onClick={() => toggleTopic(topic)} className={`rounded-full px-3 py-2 text-xs font-semibold ${scope.includes(topic) ? "bg-mint text-emerald-800" : "bg-slate-100 text-slate-600"}`}>{topic}</button>) : <span className="rounded-xl bg-sky/40 p-3 text-sm text-slate-600">Generate a Learning Flow first for topic-level selection, or continue with the whole course.</span>}</div><button disabled={busy === "generate"} onClick={() => generate()} className="primary-button mt-6 disabled:cursor-wait disabled:opacity-90">{busy === "generate" ? "Generating and verifying…" : "Generate custom assessment"}<Sparkles size={17}/></button></section><aside className="space-y-5"><section className="glass-card bg-mint/40 p-5"><Target className="text-emerald-700"/><h2 className="mt-3 font-bold">What makes it adaptive?</h2><p className="mt-2 text-sm leading-6 text-slate-600">Every submitted answer updates your topic mastery and creates a permanent report visible in Progress and History.</p></section>{mastery.length > 0 && <section className="glass-card p-5"><p className="eyebrow">Current mastery</p><div className="mt-4 space-y-3">{mastery.slice(0, 5).map(item => <div key={item.topic}><div className="flex justify-between text-xs"><span>{item.topic}</span><b>{Math.round(item.mastery * 100)}%</b></div><div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-plum" style={{ width: `${item.mastery * 100}%` }}/></div></div>)}</div></section>}</aside></div>}
    {busy === "generate" && <WorkingState title="Creating and checking your assessment" detail="The local model is drafting questions, independently verifying every answer, checking citations and removing repetitions."/>}
    {error && <div className="rounded-2xl bg-peach p-4 text-sm text-slate-700">{error}</div>}
    {recent.length > 0 && <section className="glass-card p-6"><h2 className="text-xl font-bold">Recent assessments</h2><div className="mt-4 grid gap-3 md:grid-cols-2">{recent.slice(0, 6).map(item => <button key={item.id} onClick={() => openAssessment(item.id)} className="rounded-xl bg-slate-50 p-4 text-left hover:bg-sky/40"><p className="font-semibold">{item.title}</p><p className="mt-1 text-xs text-slate-500">{item.course_name} · {item.status === "completed" ? `${item.score}%` : "Ready to take"}</p></button>)}</div></section>}</div>;

  return <div className="space-y-5"><header className="flex flex-wrap items-end justify-between gap-4"><div><p className="eyebrow">{assessment.status === "completed" || report ? "Assessment report" : "Assessment in progress"}</p><h1 className="mt-1 text-2xl font-extrabold">{assessment.title}</h1><p className="mt-2 text-sm text-slate-600">{assessment.questions.length} verified questions · {assessment.config.difficulty} difficulty</p></div><div className="flex gap-2"><DownloadMenu label={report ? "Download report" : "Download question paper"} href={`${api}/api/assessments/${assessment.id}/download`}/><button onClick={reset} className="secondary-button"><RefreshCw size={16}/> New assessment</button></div></header>
    {!report && <div className="space-y-5">{assessment.questions.map((question, index) => <section key={question.question_id} className="glass-card p-6"><div className="flex flex-wrap items-center justify-between gap-2"><p className="eyebrow">Question {index + 1} · {question.topic}</p><span className="rounded-full bg-lilac px-3 py-1 text-xs font-bold capitalize text-plum">{question.difficulty} · {question.question_type.replace("_", " ")}</span></div><h2 className="mt-3 text-lg font-bold leading-7">{question.prompt}</h2><div className="mt-4">{["mcq", "true_false"].includes(question.question_type) ? <div className="grid gap-2 sm:grid-cols-2">{question.options.map(option => <label key={option} className={`cursor-pointer rounded-xl border p-3 text-sm ${answers[question.question_id] === option ? "border-plum bg-lilac/45" : "border-slate-100 bg-slate-50"}`}><input className="mr-2 accent-[#7564a8]" type="radio" name={question.question_id} checked={answers[question.question_id] === option} onChange={() => setAnswers(current => ({ ...current, [question.question_id]: option }))}/>{option}</label>)}</div> : <textarea rows="3" value={answers[question.question_id] || ""} onChange={event => setAnswers(current => ({ ...current, [question.question_id]: event.target.value }))} className="w-full rounded-xl border border-slate-200 p-3 outline-none focus:border-plum" placeholder={question.question_type === "numerical" ? "Enter a numerical value" : question.question_type === "fill_blank" ? "Enter the missing word or phrase" : "Write your answer in your own words"}/>}</div><div className="mt-5"><p className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-400">Question source</p><SourceReferences evidence={question.evidence} api={api} compact/></div></section>)}<button disabled={busy === "submit"} onClick={submit} className="primary-button disabled:opacity-50">{busy === "submit" ? "Grading answers…" : "Submit assessment"}<ArrowRight size={17}/></button></div>}
    {busy === "submit" && <WorkingState title="Grading and updating mastery" detail="Checking each answer, identifying misconceptions and saving your permanent assessment report."/>}
    {report && <div className="space-y-5"><section className="glass-card bg-gradient-to-br from-lilac/60 to-mint/60 p-6"><p className="eyebrow">Your result</p><div className="mt-2 flex flex-wrap items-end gap-4"><p className="text-4xl font-extrabold text-plum">{report.percentage}%</p><p className="pb-1 text-sm text-slate-600">{report.correct_questions} of {report.total_questions} questions correct</p></div>{report.weak_topics.length > 0 ? <p className="mt-4 text-sm"><b>Revise next:</b> {report.weak_topics.join(", ")}</p> : <p className="mt-4 text-sm font-semibold text-emerald-700">Strong result—no topic fell below the 70% review threshold.</p>}</section><div className="space-y-4">{report.feedback.map((item, index) => <section key={item.question_id} className={`glass-card border-l-4 p-5 ${item.correct ? "border-l-emerald-400" : "border-l-rose-300"}`}><div className="flex items-center gap-2">{item.correct ? <CheckCircle2 className="text-emerald-600"/> : <XCircle className="text-rose-500"/>}<p className="font-bold">Question {index + 1} · {item.topic}</p></div><p className="mt-3 font-semibold">{item.prompt}</p><p className="mt-3 text-sm text-slate-600"><b>Your answer:</b> {item.response || "No answer"}</p><p className="mt-1 text-sm text-slate-600"><b>Correct answer:</b> {item.correct_answer}</p><p className="mt-3 rounded-xl bg-sky/35 p-3 text-sm leading-6 text-slate-700">{item.feedback}</p>{item.misconception && <p className="mt-3 text-sm text-rose-700"><b>Likely misconception:</b> {item.misconception}</p>}<div className="mt-4 space-y-1 text-xs text-slate-500">{item.citations.map((citation, citationIndex) => <p key={citationIndex}>Source: {citation.label}</p>)}</div></section>)}</div></div>}
    {error && <div className="rounded-2xl bg-peach p-4 text-sm text-slate-700">{error}</div>}
  </div>;
}

function QuickTest({ title, detail, onClick }) {
  return <button disabled={false} onClick={onClick} className="glass-card p-5 text-left transition hover:-translate-y-0.5 hover:bg-lilac/30"><Sparkles className="text-plum" size={21}/><h2 className="mt-3 font-bold">{title}</h2><p className="mt-2 text-sm leading-6 text-slate-600">{detail}</p><span className="mt-4 inline-flex items-center gap-1 text-sm font-bold text-plum">Generate and begin <ArrowRight size={15}/></span></button>;
}
