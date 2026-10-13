import React, { useEffect, useState } from "react";
import { BarChart3, BookOpenCheck, CheckCircle2, Download, Eye, Target, XCircle } from "lucide-react";
import WorkingState from "./WorkingState.jsx";
import DownloadMenu from "./DownloadMenu.jsx";

export default function ProgressPage({ api, workspace, setPage, selectCourse }) {
  const [progress, setProgress] = useState(null);
  const [allProgress, setAllProgress] = useState([]);
  const [assessment, setAssessment] = useState(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");

  async function loadProgress() {
    setBusy(true); setError("");
    try {
      const [response, allResponse] = await Promise.all([fetch(`${api}/api/progress`), fetch(`${api}/api/progress/all`)]);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not load progress.");
      setProgress(data);
      if (allResponse.ok) setAllProgress((await allResponse.json()).workspaces || []);
    } catch (issue) { setError(issue.message); } finally { setBusy(false); }
  }

  async function openReport(id) {
    setBusy(true); setError("");
    try {
      const response = await fetch(`${api}/api/assessments/${id}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not open that report.");
      setAssessment(data);
    } catch (issue) { setError(issue.message); } finally { setBusy(false); }
  }

  useEffect(() => { loadProgress(); setAssessment(null); }, [workspace.id]);

  if (busy && !progress) return <WorkingState title="Loading your learning progress" detail="Collecting assessment reports and topic mastery from this workspace."/>;
  const mastery = progress?.mastery || [];
  return <div className="space-y-5">
    <PageTitle/>
    {error && <div className="rounded-2xl bg-peach p-4 text-sm text-slate-700">{error}</div>}
    <div className="grid gap-4 sm:grid-cols-3">
      <Metric icon={<BookOpenCheck/>} label="Completed tests" value={progress?.completed_assessments || 0}/>
      <Metric icon={<BarChart3/>} label="Average score" value={progress?.average_score == null ? "—" : `${progress.average_score}%`}/>
      <Metric icon={<Target/>} label="Questions answered" value={progress?.answered_questions || 0}/>
    </div>
    <div className="grid gap-5 lg:grid-cols-[.85fr_1.15fr]">
      <section className="glass-card p-5"><p className="eyebrow">Topic mastery</p><h2 className="mt-1 text-lg font-bold">What to revise next</h2>{mastery.length ? <div className="mt-5 space-y-4">{mastery.map(item => <div key={item.topic}><div className="flex justify-between gap-3 text-sm"><span className="truncate font-medium">{item.topic}</span><span className="shrink-0 font-bold text-plum">{Math.round(item.mastery * 100)}% · {item.attempts} attempt{item.attempts === 1 ? "" : "s"}</span></div><div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-gradient-to-r from-plum to-[#9b8dcc]" style={{ width: `${item.mastery * 100}%` }}/></div></div>)}</div> : <p className="mt-4 rounded-xl bg-sky/35 p-4 text-sm text-slate-600">Complete an assessment to create your first mastery estimate.</p>}</section>
      <section className="glass-card p-5"><p className="eyebrow">Assessment reports</p><h2 className="mt-1 text-lg font-bold">Review every attempt</h2><div className="mt-4 space-y-2">{progress?.recent_assessments?.length ? progress.recent_assessments.map(item => <div key={item.id} className="flex items-center justify-between gap-3 rounded-xl bg-slate-50 p-3"><div className="min-w-0"><p className="truncate text-sm font-semibold">{item.title}</p><p className="mt-1 text-xs text-slate-500">{item.score}% · {new Date(item.created_at).toLocaleDateString()}</p></div><div className="flex gap-2"><button title="View mistakes and feedback" onClick={() => openReport(item.id)} className="icon-button"><Eye size={16}/></button><DownloadMenu compact label="Download report" href={`${api}/api/assessments/${item.id}/download`}/></div></div>) : <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-500">Your completed assessments will be stored here.</p>}</div></section>
    </div>
    {allProgress.some(item => item.course_id !== workspace.id && item.completed_assessments > 0) && <section className="glass-card p-5"><p className="eyebrow">Saved progress in other workspaces</p><h2 className="mt-1 text-lg font-bold">Your completed tests are kept with their course</h2><p className="mt-1 text-sm text-slate-600">Switch to a workspace below to see its mastery bars and full reports. Nothing has been lost.</p><div className="mt-4 grid gap-3 sm:grid-cols-2">{allProgress.filter(item => item.course_id !== workspace.id && item.completed_assessments > 0).map(item => <button key={item.course_id} onClick={() => selectCourse(item.course_id, "Progress")} className="rounded-xl bg-lilac/45 p-4 text-left transition hover:bg-lilac"><p className="font-bold">{item.course_name}</p><p className="mt-1 text-sm text-slate-600">{item.completed_assessments} completed test{item.completed_assessments === 1 ? "" : "s"} · {item.average_score}% average</p><span className="mt-2 inline-block text-xs font-bold text-plum">Open this progress →</span></button>)}</div></section>}
    {busy && progress && <WorkingState title="Opening assessment report" detail="Loading your answers, feedback, citations and misconceptions."/>}
    {assessment?.report && <ReportDetails api={api} assessment={assessment}/>} 
  </div>;
}

function PageTitle() { return <header><p className="eyebrow">Your learning journey</p><h1 className="mt-1 text-2xl font-extrabold">Progress and assessment reports</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">See mastery by topic and reopen any completed test to understand every mistake.</p></header>; }
function Metric({ icon, label, value }) { return <div className="glass-card p-4"><div className="flex items-center gap-3"><span className="grid h-9 w-9 place-items-center rounded-xl bg-lilac text-plum">{icon}</span><div><p className="text-xs text-slate-500">{label}</p><p className="text-xl font-extrabold">{value}</p></div></div></div>; }
function ReportDetails({ api, assessment }) { const report = assessment.report; return <section className="space-y-4"><div className="glass-card flex flex-wrap items-center justify-between gap-3 bg-gradient-to-r from-lilac/60 to-mint/50 p-5"><div><p className="eyebrow">Saved report</p><h2 className="mt-1 text-xl font-bold">{assessment.title}</h2><p className="mt-1 text-sm text-slate-600">{report.percentage}% · {report.correct_questions} of {report.total_questions} correct</p></div><DownloadMenu label="Download report" href={`${api}/api/assessments/${assessment.id}/download`}/></div>{report.feedback.map((item, index) => <article key={item.question_id} className={`glass-card border-l-4 p-5 ${item.correct ? "border-l-emerald-400" : "border-l-rose-300"}`}><div className="flex items-center gap-2">{item.correct ? <CheckCircle2 className="text-emerald-600" size={19}/> : <XCircle className="text-rose-500" size={19}/>}<p className="font-bold">Question {index + 1} · {item.topic}</p></div><p className="mt-2 text-sm font-semibold">{item.prompt}</p><div className="mt-3 grid gap-1 text-sm text-slate-600"><p><b>Your answer:</b> {item.response || "No answer"}</p><p><b>Correct answer:</b> {item.correct_answer}</p></div><p className="mt-3 rounded-xl bg-sky/35 p-3 text-sm leading-6 text-slate-700">{item.feedback}</p>{item.misconception && <p className="mt-2 text-sm text-rose-700"><b>Likely misconception:</b> {item.misconception}</p>}</article>)}</section>; }
