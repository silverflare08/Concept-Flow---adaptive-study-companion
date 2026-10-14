import React, { useEffect, useMemo, useState } from "react";
import { generationFetch as fetch } from "./generationFetch.js";
import {
  ArrowLeft, ArrowRight, BrainCircuit, Calculator, CheckCircle2, FileQuestion,
  Gauge, ListChecks, PenLine, RefreshCw, Sparkles, Target, Timer, XCircle, Zap,
} from "lucide-react";
import { SourceReferences } from "./StudyViews.jsx";
import WorkingState from "./WorkingState.jsx";
import DownloadMenu from "./DownloadMenu.jsx";
import RichStudyText from "./RichStudyText.jsx";

const TYPES = [
  ["mcq", "Multiple choice"], ["short_answer", "Short answer"],
  ["numerical", "Numerical"], ["true_false", "True / false"],
  ["fill_blank", "Fill in the blank"],
];

export default function AssessmentPage({ api, workspace, guide, refreshLibrary }) {
  const topics = useMemo(() => Array.from(new Set(guide?.concepts?.map(item => item.topic).filter(Boolean) || [])), [guide]);
  const [scope, setScope] = useState([]), [count, setCount] = useState(5);
  const [difficulty, setDifficulty] = useState("medium"), [types, setTypes] = useState(["mcq", "short_answer"]);
  const [assessment, setAssessment] = useState(null), [answers, setAnswers] = useState({}), [report, setReport] = useState(null);
  const [mastery, setMastery] = useState([]), [recent, setRecent] = useState([]);
  const [busy, setBusy] = useState(""), [error, setError] = useState("");
  const [builderMode, setBuilderMode] = useState("quick"), [assessmentLanguage, setAssessmentLanguage] = useState("english");
  const [testLayout, setTestLayout] = useState("focus"), [activeQuestion, setActiveQuestion] = useState(0);

  async function refreshAssessments() {
    const response = await fetch(`${api}/api/assessments`);
    if (response.ok) { const data = await response.json(); setRecent(data.assessments); setMastery(data.mastery); }
  }
  useEffect(() => { refreshAssessments(); }, [workspace.id]);

  async function generate(preset = null) {
    const config = { ...(preset || { scope, question_count: count, difficulty, question_types: types }), language: assessmentLanguage };
    if (!config.question_types.length) { setError("Select at least one question type."); return; }
    setBusy("generate"); setError(""); setReport(null);
    try {
      const response = await fetch(`${api}/api/assessments`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(config) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not generate the assessment.");
      setAssessment(data); setAnswers({}); setActiveQuestion(0);
      await refreshAssessments(); await refreshLibrary();
    } catch (issue) { setError(issue.message); } finally { setBusy(""); }
  }

  async function submit() {
    setBusy("submit"); setError("");
    try {
      const response = await fetch(`${api}/api/assessments/${assessment.id}/submit`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ answers }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not grade this assessment.");
      setReport(data.report); setMastery(data.mastery); await refreshAssessments(); await refreshLibrary();
    } catch (issue) { setError(issue.message); } finally { setBusy(""); }
  }

  async function openAssessment(id) {
    setBusy("open"); setError("");
    try {
      const response = await fetch(`${api}/api/assessments/${id}`); const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not open the assessment.");
      setAssessment(data); setReport(data.report); setActiveQuestion(0);
      setAnswers(Object.fromEntries((data.answers || []).map(item => [item.question_id, item.response])));
    } catch (issue) { setError(issue.message); } finally { setBusy(""); }
  }

  function reset() { setAssessment(null); setReport(null); setAnswers({}); setActiveQuestion(0); setError(""); }
  function toggle(value, values, setter) { setter(values.includes(value) ? values.filter(item => item !== value) : [...values, value]); }

  if (!workspace.source_count) return <EmptyAssessment/>;
  if (!assessment) return <AssessmentBuilder {...{
    api, builderMode, setBuilderMode, assessmentLanguage, setAssessmentLanguage, generate,
    mastery, scope, setScope, count, setCount, difficulty, setDifficulty, types, setTypes,
    topics, recent, openAssessment, busy, error, toggle,
  }}/>;

  const visibleQuestions = testLayout === "focus" ? [assessment.questions[activeQuestion]].filter(Boolean) : assessment.questions;
  return <div className="space-y-5">
    <header className="flex flex-wrap items-end justify-between gap-4"><div><p className="eyebrow">{report ? "Assessment report" : "Assessment in progress"}</p><h1 className="mt-1 text-2xl font-extrabold">{assessment.title}</h1><p className="mt-2 text-sm text-slate-600">{assessment.questions.length} verified questions · {assessment.config.difficulty} difficulty</p></div><div className="flex flex-wrap gap-2"><DownloadMenu label={report ? "Download report" : "Download question paper"} href={`${api}/api/assessments/${assessment.id}/download`}/><button onClick={reset} className="secondary-button"><RefreshCw size={16}/>New assessment</button></div></header>

    {!report && <>
      <section className="glass-card flex flex-wrap items-center justify-between gap-3 p-4"><div><p className="text-sm font-bold">Choose your test experience</p><p className="text-xs text-slate-500">Focus on one question or view the complete paper.</p></div><div className="flex rounded-xl bg-slate-100 p-1"><ModeButton active={testLayout === "focus"} onClick={() => setTestLayout("focus")} icon={Gauge} label="Focus mode"/><ModeButton active={testLayout === "paper"} onClick={() => setTestLayout("paper")} icon={ListChecks} label="Full paper"/></div></section>
      <div className="space-y-5">{visibleQuestions.map((question, index) => <QuestionCard key={question.question_id} question={question} number={testLayout === "focus" ? activeQuestion + 1 : index + 1} answer={answers[question.question_id] || ""} setAnswer={value => setAnswers(current => ({ ...current, [question.question_id]: value }))} api={api}/>)}</div>
      {testLayout === "focus" && <FocusNavigator assessment={assessment} answers={answers} active={activeQuestion} setActive={setActiveQuestion}/>}
      <button disabled={busy === "submit"} onClick={submit} className="primary-button disabled:opacity-50">{busy === "submit" ? "Grading answers…" : "Submit assessment"}<ArrowRight size={17}/></button>
    </>}
    {busy === "submit" && <WorkingState title="Grading and updating mastery" detail="Checking each answer, identifying misconceptions and saving your permanent report."/>}
    {report && <AssessmentReport report={report} api={api}/>}
    {error && <div className="rounded-2xl bg-peach p-4 text-sm text-slate-700">{error}</div>}
  </div>;
}

function AssessmentBuilder(props) {
  const weakTopics = props.mastery.filter(item => item.mastery < .7).slice(0, 3).map(item => item.topic);
  return <div className="space-y-5">
    <header><p className="eyebrow">Adaptive assessment</p><h1 className="mt-1 text-2xl font-extrabold">Choose how you want to practise</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">Every question is generated from your material, independently checked and saved with a worked solution.</p></header>
    <div className="flex gap-2 rounded-2xl bg-white/70 p-2"><button onClick={() => props.setBuilderMode("quick")} className={props.builderMode === "quick" ? "primary-button" : "secondary-button"}>Practice styles</button><button onClick={() => props.setBuilderMode("custom")} className={props.builderMode === "custom" ? "primary-button" : "secondary-button"}>Build my own</button></div>
    <LanguagePicker value={props.assessmentLanguage} setValue={props.setAssessmentLanguage}/>
    {props.builderMode === "quick" ? <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      <QuickTest icon={Zap} tone="sky" title="Rapid recall" badge="5 min" detail="Five objective questions for a quick memory check." onClick={() => props.generate({ scope: [], question_count: 5, difficulty: "easy", question_types: ["mcq", "true_false", "fill_blank"] })}/>
      <QuickTest icon={BrainCircuit} tone="lilac" title="Diagnostic check" badge="Find my level" detail="A balanced test that establishes strengths and developing topics." onClick={() => props.generate({ scope: [], question_count: 8, difficulty: "medium", question_types: ["mcq", "short_answer", "true_false"] })}/>
      <QuickTest icon={Target} tone="mint" title="Weak-topic booster" badge="Adaptive" detail="Prioritises topics currently below 70% mastery." onClick={() => props.generate({ scope: weakTopics, question_count: 6, difficulty: "medium", question_types: ["mcq", "short_answer", "fill_blank"] })}/>
      <QuickTest icon={Timer} tone="peach" title="Exam simulator" badge="Deep practice" detail="A longer, difficult paper with objective and written questions." onClick={() => props.generate({ scope: [], question_count: 12, difficulty: "hard", question_types: ["mcq", "short_answer", "numerical", "fill_blank"] })}/>
      <QuickTest icon={PenLine} tone="rose" title="Written-answer practice" badge="Explain clearly" detail="Build understanding through source-cited written answers." onClick={() => props.generate({ scope: [], question_count: 6, difficulty: "medium", question_types: ["short_answer"] })}/>
      <QuickTest icon={Calculator} tone="amber" title="Numerical workout" badge="Problem solving" detail="Calculation-oriented questions wherever your material supports them." onClick={() => props.generate({ scope: [], question_count: 6, difficulty: "hard", question_types: ["numerical", "fill_blank"] })}/>
    </div> : <CustomBuilder {...props}/>}
    {props.busy === "generate" && <WorkingState title="Creating and checking your assessment" detail="Drafting questions, checking every answer against its source and removing repetitions."/>}
    {props.error && <div className="rounded-2xl bg-peach p-4 text-sm text-slate-700">{props.error}</div>}
    {props.recent.length > 0 && <section className="glass-card p-6"><h2 className="text-xl font-bold">Recent assessments</h2><div className="mt-4 grid gap-3 md:grid-cols-2">{props.recent.slice(0, 6).map(item => <button key={item.id} onClick={() => props.openAssessment(item.id)} className="rounded-xl bg-slate-50 p-4 text-left transition hover:bg-sky/40"><p className="font-semibold">{item.title}</p><p className="mt-1 text-xs text-slate-500">{item.course_name} · {item.status === "completed" ? `${item.score}%` : "Ready to take"}</p></button>)}</div></section>}
  </div>;
}

function CustomBuilder(props) {
  return <div className="grid gap-6 lg:grid-cols-[1.2fr_.8fr]"><section className="glass-card p-5"><label className="text-sm font-bold">Number of questions: {props.count}</label><input className="mt-3 w-full accent-[#7564a8]" type="range" min="1" max="12" value={props.count} onChange={event => props.setCount(Number(event.target.value))}/><h2 className="mt-5 text-sm font-bold">Difficulty</h2><div className="mt-3 flex gap-2">{["easy", "medium", "hard"].map(item => <button key={item} onClick={() => props.setDifficulty(item)} className={`rounded-full px-4 py-2 text-sm font-semibold capitalize ${props.difficulty === item ? "bg-plum text-white" : "bg-slate-100 text-slate-600"}`}>{item}</button>)}</div><h2 className="mt-5 text-sm font-bold">Question types</h2><div className="mt-3 grid gap-2 sm:grid-cols-3">{TYPES.map(([value, label]) => <button key={value} onClick={() => props.toggle(value, props.types, props.setTypes)} className={`rounded-xl border p-3 text-left text-sm font-semibold ${props.types.includes(value) ? "border-plum bg-lilac/60 text-plum" : "border-slate-100 bg-slate-50 text-slate-600"}`}>{label}</button>)}</div><h2 className="mt-5 text-sm font-bold">Topic scope</h2><p className="mt-1 text-xs text-slate-500">Leave unselected for automatic weak-topic selection.</p><div className="mt-3 flex flex-wrap gap-2">{props.topics.length ? props.topics.map(topic => <button key={topic} onClick={() => props.toggle(topic, props.scope, props.setScope)} className={`rounded-full px-3 py-2 text-xs font-semibold ${props.scope.includes(topic) ? "bg-mint text-emerald-800" : "bg-slate-100 text-slate-600"}`}>{topic}</button>) : <span className="rounded-xl bg-sky/40 p-3 text-sm text-slate-600">Generate a Learning Flow for topic-level selection.</span>}</div><button disabled={props.busy === "generate"} onClick={() => props.generate()} className="primary-button mt-6 disabled:opacity-60">Generate custom assessment<Sparkles size={17}/></button></section><aside className="space-y-4"><section className="glass-card bg-mint/40 p-5"><Target className="text-emerald-700"/><h2 className="mt-3 font-bold">Adaptive by design</h2><p className="mt-2 text-sm leading-6 text-slate-600">Leave topics blank and ConceptFlow prioritises developing topics from your learner model.</p></section>{props.mastery.length > 0 && <section className="glass-card p-5"><p className="eyebrow">Current mastery</p><div className="mt-4 space-y-3">{props.mastery.slice(0, 5).map(item => <div key={item.topic}><div className="flex justify-between text-xs"><span>{item.topic}</span><b>{Math.round(item.mastery * 100)}%</b></div><div className="mt-1 h-2 rounded-full bg-slate-100"><div className="h-full rounded-full bg-plum" style={{ width: `${item.mastery * 100}%` }}/></div></div>)}</div></section>}</aside></div>;
}

function QuestionCard({ question, number, answer, setAnswer, api }) {
  return <section className="glass-card p-6"><div className="flex flex-wrap items-center justify-between gap-2"><p className="eyebrow">Question {number} · {question.topic}</p><span className="rounded-full bg-lilac px-3 py-1 text-xs font-bold capitalize text-plum">{question.difficulty} · {question.question_type.replace("_", " ")}</span></div><div className="mt-3"><RichStudyText text={question.prompt}/></div><div className="mt-4">{["mcq", "true_false"].includes(question.question_type) ? <div className="grid gap-2 sm:grid-cols-2">{question.options.map(option => <label key={option} className={`cursor-pointer rounded-xl border p-3 text-sm transition ${answer === option ? "border-plum bg-lilac/45" : "border-slate-100 bg-slate-50 hover:bg-sky/30"}`}><input className="mr-2 accent-[#7564a8]" type="radio" name={question.question_id} checked={answer === option} onChange={() => setAnswer(option)}/>{option}</label>)}</div> : <textarea rows="3" value={answer} onChange={event => setAnswer(event.target.value)} className="w-full rounded-xl border border-slate-200 p-3 outline-none focus:border-plum" placeholder={question.question_type === "numerical" ? "Enter a numerical value" : question.question_type === "fill_blank" ? "Enter the missing word or phrase" : "Write your answer in your own words"}/>}</div><div className="mt-5"><p className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-400">Verified question source</p><SourceReferences evidence={question.evidence} api={api} compact/></div></section>;
}

function FocusNavigator({ assessment, answers, active, setActive }) {
  return <div className="glass-card flex flex-wrap items-center justify-between gap-3 p-4">
    <button disabled={active === 0} onClick={() => setActive(value => value - 1)} className="secondary-button disabled:opacity-40"><ArrowLeft size={16}/>Previous</button>
    <div className="min-w-44 flex-1">
      <div className="flex justify-between text-xs font-bold text-slate-500"><span>{Object.keys(answers).length} answered</span><span>{active + 1} / {assessment.questions.length}</span></div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-plum transition-all" style={{ width: `${((active + 1) / assessment.questions.length) * 100}%` }}/></div>
      <div className="mt-3 flex flex-wrap justify-center gap-1.5">{assessment.questions.map((question, index) => <button key={question.question_id} aria-label={`Open question ${index + 1}`} onClick={() => setActive(index)} className={`h-2.5 w-2.5 rounded-full ${index === active ? "bg-plum ring-2 ring-lavender" : answers[question.question_id] ? "bg-emerald-400" : "bg-slate-200"}`}/>)}</div>
    </div>
    <button disabled={active === assessment.questions.length - 1} onClick={() => setActive(value => value + 1)} className="secondary-button disabled:opacity-40">Next<ArrowRight size={16}/></button>
  </div>;
}

function AssessmentReport({ report, api }) {
  return <div className="space-y-5"><section className="glass-card bg-gradient-to-br from-lilac/60 to-mint/60 p-6"><p className="eyebrow">Your result</p><div className="mt-2 flex items-end gap-4"><p className="text-4xl font-extrabold text-plum">{report.percentage}%</p><p className="pb-1 text-sm text-slate-600">{report.correct_questions} of {report.total_questions} correct</p></div>{report.weak_topics.length ? <p className="mt-4 text-sm"><b>Revise next:</b> {report.weak_topics.join(", ")}</p> : <p className="mt-4 text-sm font-semibold text-emerald-700">Strong result—no topic fell below the review threshold.</p>}</section>{report.feedback.map((item, index) => <section key={item.question_id} className={`glass-card border-l-4 p-5 ${item.correct ? "border-l-emerald-400" : "border-l-rose-300"}`}><div className="flex items-center gap-2">{item.correct ? <CheckCircle2 className="text-emerald-600"/> : <XCircle className="text-rose-500"/>}<p className="font-bold">Question {index + 1} · {item.topic}</p></div><div className="mt-3"><RichStudyText text={item.prompt}/></div><div className="mt-3 rounded-xl bg-slate-50 p-3 text-sm text-slate-600"><p><b>Your answer:</b> {item.response || "No answer"}</p><p><b>Correct answer:</b> {item.correct_answer}</p></div><div className="mt-3 rounded-xl bg-sky/35 p-4"><p className="eyebrow mb-2">Personal feedback</p><RichStudyText text={item.feedback}/></div><div className="mt-3 rounded-xl bg-mint/35 p-4"><p className="eyebrow mb-2">Worked solution</p><RichStudyText text={item.explanation}/></div>{item.misconception && <p className="mt-3 text-sm text-rose-700"><b>Likely misconception:</b> {item.misconception}</p>}<div className="mt-4 space-y-1 text-xs text-slate-500">{item.citations.map((citation, citationIndex) => <p key={citationIndex}>Source: {citation.label}</p>)}</div></section>)}</div>;
}

function LanguagePicker({ value, setValue }) { return <section className="glass-card flex flex-wrap items-center justify-between gap-3 p-4"><div><p className="text-sm font-bold">Question and solution language</p><p className="text-xs text-slate-500">The test and worked feedback use your selected language.</p></div><div className="flex rounded-xl bg-slate-100 p-1">{[["english", "English"], ["hindi", "हिंदी"], ["hinglish", "Hinglish"]].map(([key, label]) => <button key={key} onClick={() => setValue(key)} className={`rounded-lg px-3 py-2 text-xs font-bold ${value === key ? "bg-white text-plum shadow-sm" : "text-slate-500"}`}>{label}</button>)}</div></section>; }
function ModeButton({ active, onClick, icon: Icon, label }) { return <button onClick={onClick} className={`rounded-lg px-3 py-2 text-xs font-bold ${active ? "bg-white text-plum shadow-sm" : "text-slate-500"}`}><Icon className="mr-1 inline" size={14}/>{label}</button>; }
function QuickTest({ icon: Icon, tone, title, badge, detail, onClick }) { const tones = { sky: "from-sky/65", lilac: "from-lilac/70", mint: "from-mint/65", peach: "from-peach/60", rose: "from-rose-100", amber: "from-amber-100" }; return <button onClick={onClick} className={`glass-card bg-gradient-to-br ${tones[tone]} to-white p-5 text-left transition hover:-translate-y-1 hover:shadow-lg`}><div className="flex items-start justify-between gap-3"><span className="grid h-10 w-10 place-items-center rounded-2xl bg-white text-plum shadow-sm"><Icon size={20}/></span><span className="rounded-full bg-white/80 px-2.5 py-1 text-[10px] font-black uppercase tracking-wide text-slate-500">{badge}</span></div><h2 className="mt-4 font-extrabold">{title}</h2><p className="mt-2 text-sm leading-6 text-slate-600">{detail}</p><span className="mt-4 inline-flex items-center gap-1 text-sm font-bold text-plum">Generate and begin<ArrowRight size={15}/></span></button>; }
function EmptyAssessment() { return <div className="space-y-6"><header><p className="eyebrow">Adaptive assessment</p><h1 className="mt-1 text-2xl font-extrabold">Practise from your own material</h1></header><div className="glass-card border-dashed p-8 text-center"><FileQuestion className="mx-auto text-plum" size={30}/><h2 className="mt-3 text-lg font-bold">Add study material first</h2><p className="mt-2 text-sm text-slate-500">Questions are generated only from evidence in the active course.</p></div></div>; }
