import React, { useEffect, useMemo, useState } from "react";
import { BarChart3, Bell, BookOpenCheck, BrainCircuit, Check, CheckCircle2, ChevronLeft, ChevronRight, Edit3, Eye, MessageSquareText, Plus, Target, Upload, XCircle } from "lucide-react";
import WorkingState from "./WorkingState.jsx";
import DownloadMenu from "./DownloadMenu.jsx";
import RichStudyText from "./RichStudyText.jsx";
import StudyPlannerDialog from "./StudyPlannerDialog.jsx";

const dateKey = value => {
  const date = new Date(value);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
};

export default function ProgressPage({ api, workspace, setPage, selectCourse, refreshReminders }) {
  const [progress, setProgress] = useState(null);
  const [allProgress, setAllProgress] = useState([]);
  const [assessment, setAssessment] = useState(null);
  const [planner, setPlanner] = useState(null);
  const [plannerBusy, setPlannerBusy] = useState(false);
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
    } catch (issue) { setError(issue.message); }
    finally { setBusy(false); }
  }

  async function openReport(id) {
    setBusy(true); setError("");
    try {
      const response = await fetch(`${api}/api/assessments/${id}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not open that report.");
      setAssessment(data);
    } catch (issue) { setError(issue.message); }
    finally { setBusy(false); }
  }

  async function savePlan(payload) {
    setPlannerBusy(true); setError("");
    try {
      const editing = planner?.event;
      const response = await fetch(`${api}/api/study-events${editing ? `/${editing.id}` : ""}`, { method: editing ? "PATCH" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not save this study plan.");
      setPlanner(null); await loadProgress(); await refreshReminders?.();
    } catch (issue) { setError(issue.message); }
    finally { setPlannerBusy(false); }
  }

  async function deletePlan(event) {
    setPlannerBusy(true); setError("");
    try {
      const response = await fetch(`${api}/api/study-events/${event.id}`, { method: "DELETE" });
      if (!response.ok) throw new Error("Could not delete this study plan.");
      setPlanner(null); await loadProgress(); await refreshReminders?.();
    } catch (issue) { setError(issue.message); }
    finally { setPlannerBusy(false); }
  }

  async function togglePlan(event) {
    const response = await fetch(`${api}/api/study-events/${event.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ completed: !event.completed }) });
    if (response.ok) { await loadProgress(); await refreshReminders?.(); }
  }

  useEffect(() => { loadProgress(); setAssessment(null); setPlanner(null); }, [workspace.id]);
  if (busy && !progress) return <WorkingState title="Loading your learning progress" detail="Reading saved answers, reports, topic accuracy and learner-model signals."/>;

  const latestScore = progress?.score_history?.at(-1)?.score;
  const masteryAverage = progress?.mastery?.length ? Math.round(progress.mastery.reduce((sum, item) => sum + item.mastery, 0) / progress.mastery.length * 100) : null;
  const otherWithTests = allProgress.filter(item => item.course_id !== workspace.id && item.completed_assessments > 0);

  return <div className="space-y-4">
    <header><p className="eyebrow">Your learning journey</p><h1 className="mt-1 text-2xl font-extrabold">Progress analytics</h1><p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">Compact, real analytics from your saved activity—plus a planner for what comes next.</p></header>
    <WorkspaceContext workspace={workspace} progress={progress} otherWithTests={otherWithTests} selectCourse={selectCourse}/>
    {error && <div className="rounded-2xl bg-peach p-4 text-sm text-slate-700">{error}</div>}
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
      <Metric icon={<BookOpenCheck/>} label="Latest score" value={latestScore == null ? "—" : `${latestScore}%`} detail="Most recent test"/>
      <Metric icon={<BarChart3/>} label="Average score" value={progress?.average_score == null ? "—" : `${progress.average_score}%`} detail={`${progress?.completed_assessments || 0} completed tests`}/>
      <Metric icon={<CheckCircle2/>} label="Correct" value={`${progress?.correct_questions || 0}/${progress?.total_questions || 0}`} detail="Saved answers" tone="good"/>
      <Metric icon={<Target/>} label="Mastery" value={masteryAverage == null ? "—" : `${masteryAverage}%`} detail="BKT estimate"/>
      <Metric icon={<BrainCircuit/>} label="Weak topics" value={progress?.weak_topics?.length || 0} detail="Need revision" tone="warn"/>
      <Metric icon={<MessageSquareText/>} label="Tutor signals" value={progress?.tutoring_interactions || 0} detail="Learning interactions"/>
    </div>
    <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_20rem]">
      <DailyPulseChart activity={progress?.daily_activity || []}/>
      <StudyCalendar activity={progress?.daily_activity || []} events={progress?.study_events || []} openReport={openReport} setPage={setPage} onAdd={date => setPlanner({ date })} onEdit={event => setPlanner({ date: dateKey(event.scheduled_for), event })} onToggle={togglePlan}/>
    </div>
    <div className="grid gap-4 xl:grid-cols-[1.35fr_.65fr]"><AssessmentScoreChart history={progress?.score_history || []}/><OutcomeDonut correct={progress?.correct_questions || 0} total={progress?.total_questions || 0}/></div>
    <div className="grid gap-4 lg:grid-cols-2"><TopicPerformanceChart topics={progress?.topic_performance || []}/><MasteryChart mastery={progress?.mastery || []}/></div>
    <div className="grid gap-4 lg:grid-cols-[1.05fr_.95fr]"><AssessmentHistory assessments={progress?.recent_assessments || []} api={api} openReport={openReport}/><RevisionPlan plan={progress?.revision_plan || []} setPage={setPage}/></div>
    {busy && progress && <WorkingState title="Opening saved progress" detail="Refreshing answers, activities and study plans."/>}
    {assessment?.report && <ReportDetails api={api} assessment={assessment}/>} 
    {planner && <StudyPlannerDialog event={planner.event} date={planner.date} busy={plannerBusy} onSave={savePlan} onDelete={deletePlan} onClose={() => setPlanner(null)}/>} 
  </div>;
}

function WorkspaceContext({ workspace, progress, otherWithTests, selectCourse }) {
  return <section className="glass-card border-l-4 border-l-plum bg-gradient-to-r from-lilac/45 to-white px-4 py-3"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-[10px] font-bold uppercase tracking-[.14em] text-plum">Analytics workspace</p><p className="mt-0.5 font-extrabold">{workspace.name}</p></div><span className="rounded-full bg-white px-3 py-1 text-xs font-bold text-slate-600 shadow-sm">{progress?.completed_assessments || 0} saved test{progress?.completed_assessments === 1 ? "" : "s"}</span></div>{!progress?.completed_assessments && otherWithTests.length > 0 && <div className="mt-3 rounded-xl bg-white/80 p-2.5 text-xs text-slate-600">Your saved tests are in {otherWithTests.map((item, index) => <React.Fragment key={item.course_id}>{index ? ", " : ""}<button className="font-bold text-plum underline" onClick={() => selectCourse(item.course_id, "Progress")}>{item.course_name}</button></React.Fragment>)}.</div>}</section>;
}

function Metric({ icon, label, value, detail, tone = "default" }) {
  const color = tone === "good" ? "bg-mint text-emerald-700" : tone === "warn" ? "bg-peach text-rose-600" : "bg-lilac text-plum";
  return <div className="glass-card p-3"><div className="flex items-center gap-2.5"><span className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg ${color}`}>{React.cloneElement(icon, { size: 16 })}</span><div className="min-w-0"><p className="truncate text-[10px] text-slate-500">{label}</p><p className="text-lg font-extrabold leading-5">{value}</p><p className="truncate text-[9px] text-slate-400">{detail}</p></div></div></div>;
}

function DailyPulseChart({ activity }) {
  const storedDays = Object.fromEntries(activity.map(day => [day.date, day]));
  const today = new Date(); today.setHours(12, 0, 0, 0);
  const days = Array.from({ length: 14 }, (_, index) => {
    const date = new Date(today); date.setDate(today.getDate() - (13 - index));
    const key = dateKey(date);
    return storedDays[key] || { date: key, total: 0, chats: 0, assessments: 0, materials: 0, assessment_score: null, mastery_gain: 0 };
  });
  const maxTotal = Math.max(1, ...days.map(day => day.total));
  const selected = [...days].reverse().find(day => day.total > 0) || days.at(-1);
  return <section className="glass-card p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="eyebrow">Daily learning pulse</p><h2 className="mt-1 text-base font-bold">Activity and progress</h2></div><div className="flex gap-3 text-[10px] text-slate-500"><span className="flex items-center gap-1"><i className="h-2 w-2 rounded-sm bg-plum"/>Actions</span><span className="flex items-center gap-1"><i className="h-2 w-2 rounded-full bg-emerald-400"/>Test score</span></div></div><div className="mt-4 flex h-32 items-end gap-2 rounded-xl bg-gradient-to-b from-sky/20 to-white px-3 pb-6 pt-3">{days.map((day, index) => <div key={day.date} className="group relative flex h-full min-w-0 flex-1 items-end" title={`${day.total} activities${day.assessment_score == null ? "" : ` · ${day.assessment_score}% test average`} · ${day.mastery_gain >= 0 ? "+" : ""}${day.mastery_gain}% mastery movement`}><div className="relative w-full"><div className={`w-full rounded-t-md ${day.total ? "bg-gradient-to-t from-plum to-lavender" : "bg-slate-100"}`} style={{ height: `${day.total ? Math.max(8, day.total / maxTotal * 88) : 3}px` }}/>{day.assessment_score != null && <span className="absolute left-1/2 grid h-5 w-5 -translate-x-1/2 place-items-center rounded-full bg-emerald-400 text-[8px] font-black text-white shadow" style={{ bottom: `${Math.max(2, day.assessment_score / 100 * 76)}px` }}>{Math.round(day.assessment_score)}</span>}</div>{(index % 2 === 1 || index === days.length - 1) && <span className="absolute -bottom-5 left-1/2 -translate-x-1/2 whitespace-nowrap text-[8px] text-slate-400">{new Date(`${day.date}T12:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</span>}</div>)}</div><div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-500"><span><b className="text-slate-700">Latest active day:</b> {new Date(`${selected.date}T12:00:00`).toLocaleDateString()}</span><span>{selected.chats} chats</span><span>{selected.assessments} tests</span><span>{selected.materials} uploads</span><span className="text-emerald-700">{selected.mastery_gain >= 0 ? "+" : ""}{selected.mastery_gain}% mastery movement</span></div></section>;
}

function AssessmentScoreChart({ history }) {
  const [selected, setSelected] = useState(null);
  if (!history.length) return <EmptyChart eyebrow="Test performance" title="Assessment scores" text="Complete an assessment to create the first score bar."/>;
  const shown = history.slice(-8), active = selected || shown.at(-1);
  return <section className="glass-card p-4"><div className="flex items-start justify-between gap-3"><div><p className="eyebrow">Test performance</p><h2 className="mt-1 text-base font-bold">Assessment scores</h2></div><span className="rounded-full bg-lilac px-2.5 py-1 text-[10px] font-bold text-plum">{active.score}% selected</span></div><div className="mt-4 flex h-36 items-end gap-2 rounded-xl bg-gradient-to-b from-sky/20 to-white px-3 pb-6 pt-5">{shown.map(item => <button key={item.id} onClick={() => setSelected(item)} className="group relative flex h-full min-w-[28px] flex-1 items-end" title={`${item.title}: ${item.score}%`}><span className={`relative block w-full rounded-t-lg bg-gradient-to-t from-plum to-lavender ${active.id === item.id ? "ring-2 ring-plum ring-offset-1" : ""}`} style={{ height: `${Math.max(item.score, 4)}%` }}><span className="absolute -top-5 left-1/2 -translate-x-1/2 text-[9px] font-bold text-plum">{item.score}</span></span><span className="absolute -bottom-5 left-1/2 -translate-x-1/2 whitespace-nowrap text-[8px] text-slate-400">{new Date(item.date).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</span></button>)}</div><p className="mt-3 truncate text-xs text-slate-500"><b>{active.title}</b> · {new Date(active.date).toLocaleString()}</p></section>;
}

function TopicPerformanceChart({ topics }) {
  const [selected, setSelected] = useState(null);
  if (!topics.length) return <EmptyChart eyebrow="Answer analysis" title="Accuracy by topic" text="Topic accuracy appears after a completed assessment report."/>;
  const active = selected || topics[0];
  return <section className="glass-card p-4"><div className="flex items-start justify-between gap-3"><div><p className="eyebrow">Answer analysis</p><h2 className="mt-1 text-base font-bold">Accuracy by tested topic</h2></div><span className="rounded-full bg-peach px-2 py-1 text-[10px] font-bold text-rose-700">Lowest first</span></div><div className="mt-3 max-h-52 space-y-2 overflow-y-auto pr-1">{topics.slice(0, 8).map(item => <button key={item.topic} onClick={() => setSelected(item)} className={`block w-full rounded-lg px-3 py-2 text-left ${active.topic === item.topic ? "bg-lilac/45 ring-1 ring-lavender" : "bg-slate-50"}`}><div className="flex justify-between gap-3 text-xs"><span className="truncate font-semibold">{item.topic}</span><b>{item.accuracy}%</b></div><div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-white"><div className={`h-full rounded-full ${item.accuracy < 45 ? "bg-rose-400" : item.accuracy < 70 ? "bg-amber-400" : "bg-emerald-400"}`} style={{ width: `${item.accuracy}%` }}/></div></button>)}</div><p className="mt-3 rounded-lg bg-slate-50 p-2 text-[11px] text-slate-600"><b>{active.topic}:</b> {active.correct} correct-equivalent / {active.questions} questions.</p></section>;
}

function OutcomeDonut({ correct, total }) {
  const percentage = total ? Math.round(correct / total * 100) : 0;
  return <section className="glass-card p-4"><p className="eyebrow">Answer outcomes</p><h2 className="mt-1 text-base font-bold">Correct vs review</h2>{total ? <><div className="mx-auto mt-4 grid h-28 w-28 place-items-center rounded-full shadow-inner" style={{ background: `conic-gradient(#6fcf9b 0 ${percentage}%, #ee9a9a ${percentage}% 100%)` }}><div className="grid h-16 w-16 place-items-center rounded-full bg-white text-center shadow-sm"><div><p className="text-lg font-black text-plum">{correct}/{total}</p><p className="text-[8px] font-bold text-slate-400">correct</p></div></div></div><div className="mt-4 grid grid-cols-2 gap-2"><Legend color="bg-emerald-400" label="Correct" value={correct}/><Legend color="bg-rose-300" label="Review" value={total - correct}/></div></> : <p className="mt-4 rounded-xl bg-slate-50 p-3 text-xs text-slate-500">No submitted answers yet.</p>}</section>;
}

function MasteryChart({ mastery }) {
  return <section className="glass-card p-4"><p className="eyebrow">Learner model</p><h2 className="mt-1 text-base font-bold">Current mastery estimate</h2><p className="mt-1 text-[11px] text-slate-500">BKT updates after answers and grounded lessons.</p>{mastery.length ? <div className="mt-3 max-h-56 space-y-3 overflow-y-auto pr-1">{mastery.map(item => { const percent = Math.round(item.mastery * 100); return <div key={item.topic}><div className="flex justify-between gap-3 text-xs"><span className="truncate font-medium">{item.topic}</span><b className={percent < 45 ? "text-rose-600" : percent < 70 ? "text-amber-600" : "text-emerald-700"}>{percent}%</b></div><div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-slate-100"><div className={`h-full rounded-full ${percent < 45 ? "bg-rose-400" : percent < 70 ? "bg-amber-400" : "bg-emerald-400"}`} style={{ width: `${percent}%` }}/></div><p className="mt-1 text-[9px] text-slate-400">{item.attempts} answers · {item.conversation_updates || 0} tutor signals</p></div>; })}</div> : <p className="mt-3 rounded-xl bg-sky/35 p-3 text-xs text-slate-600">Use tutoring or submit an assessment to initialise mastery.</p>}</section>;
}

function StudyCalendar({ activity, events, openReport, setPage, onAdd, onEdit, onToggle }) {
  const today = new Date();
  const [cursor, setCursor] = useState(new Date(today.getFullYear(), today.getMonth(), 1));
  const [selectedDate, setSelectedDate] = useState(dateKey(today));
  const activityMap = useMemo(() => Object.fromEntries(activity.map(item => [item.date, item])), [activity]);
  const eventMap = useMemo(() => events.reduce((map, event) => { const key = dateKey(event.scheduled_for); (map[key] ||= []).push(event); return map; }, {}), [events]);
  const year = cursor.getFullYear(), month = cursor.getMonth();
  const first = new Date(year, month, 1), days = new Date(year, month + 1, 0).getDate();
  const cells = [...Array(first.getDay()).fill(null), ...Array.from({ length: days }, (_, index) => index + 1)];
  const keyFor = day => `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  const selectedActivity = activityMap[selectedDate];
  const selectedEvents = eventMap[selectedDate] || [];
  const browserAlerts = typeof Notification !== "undefined" ? Notification.permission : "unsupported";
  async function enableNotifications() { if (browserAlerts === "default") await Notification.requestPermission(); }
  return <section className="glass-card p-3.5"><div className="flex items-start justify-between gap-2"><div><p className="eyebrow">Study calendar</p><h2 className="mt-0.5 text-sm font-bold">{cursor.toLocaleDateString(undefined, { month: "long", year: "numeric" })}</h2></div><div className="flex"><button aria-label="Previous month" className="icon-button h-8 w-8" onClick={() => setCursor(new Date(year, month - 1, 1))}><ChevronLeft size={15}/></button><button aria-label="Next month" className="icon-button h-8 w-8" onClick={() => setCursor(new Date(year, month + 1, 1))}><ChevronRight size={15}/></button></div></div><div className="mt-3 grid grid-cols-7 gap-1 text-center text-[9px] font-bold text-slate-400">{["S", "M", "T", "W", "T", "F", "S"].map((day, index) => <span key={`${day}-${index}`}>{day}</span>)}</div><div className="mt-1.5 grid grid-cols-7 gap-1">{cells.map((day, index) => { if (!day) return <span key={`blank-${index}`} className="h-9"/>; const key = keyFor(day), item = activityMap[key], plans = eventMap[key] || [], selected = key === selectedDate; return <button key={key} onClick={() => setSelectedDate(key)} title={`${item?.total || 0} recorded activities · ${plans.length} plans`} className={`relative h-9 rounded-lg text-[11px] font-semibold ${selected ? "bg-plum text-white ring-2 ring-lavender" : item?.total ? "bg-lilac/65 text-plum" : "bg-slate-50 text-slate-500"}`}><span>{day}</span><span className="absolute bottom-1 left-1/2 flex -translate-x-1/2 gap-0.5">{item?.chats > 0 && <i className="h-1 w-1 rounded-full bg-sky-500"/>}{item?.assessments > 0 && <i className="h-1 w-1 rounded-full bg-emerald-500"/>}{item?.materials > 0 && <i className="h-1 w-1 rounded-full bg-amber-500"/>}{plans.length > 0 && <i className="h-1 w-1 rounded-full bg-rose-400"/>}</span></button>; })}</div><div className="mt-3 flex flex-wrap gap-2 text-[9px] text-slate-500"><span>● Chat</span><span className="text-emerald-600">● Test</span><span className="text-amber-600">● Upload</span><span className="text-rose-500">● Plan</span></div><div className="mt-3 rounded-xl bg-slate-50 p-2.5"><div className="flex items-center justify-between gap-2"><div><p className="text-[10px] font-bold text-slate-500">{new Date(`${selectedDate}T12:00:00`).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}</p><p className="text-[11px] font-semibold">{(selectedActivity?.total || 0) + selectedEvents.length} items</p></div><button onClick={() => onAdd(selectedDate)} className="inline-flex items-center gap-1 rounded-lg bg-plum px-2 py-1.5 text-[10px] font-bold text-white"><Plus size={12}/> Add plan</button></div><div className="mt-2 max-h-44 space-y-1.5 overflow-y-auto">{selectedEvents.map(event => <div key={event.id} className={`rounded-lg bg-white p-2 ${event.completed ? "opacity-55" : ""}`}><div className="flex items-start gap-2"><button title={event.completed ? "Mark active" : "Mark complete"} onClick={() => onToggle(event)} className={`mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full ${event.completed ? "bg-mint text-emerald-700" : "border border-slate-300"}`}>{event.completed && <Check size={12}/>}</button><button onClick={() => onEdit(event)} className="min-w-0 flex-1 text-left"><p className={`truncate text-[11px] font-bold ${event.completed ? "line-through" : ""}`}>{event.title}</p><p className="text-[9px] text-slate-400">{new Date(event.scheduled_for).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })} · {event.kind}</p></button><button title="Amend plan" onClick={() => onEdit(event)} className="text-slate-400"><Edit3 size={12}/></button></div></div>)}{selectedActivity?.activities?.map((item, index) => <button key={`${item.type}-${item.id}-${index}`} onClick={() => item.type === "assessment" ? openReport(item.id) : item.type === "chat" ? setPage("History") : null} className="flex w-full items-center gap-2 rounded-lg bg-white p-2 text-left"><ActivityIcon type={item.type}/><span className="min-w-0 flex-1"><span className="block truncate text-[11px] font-semibold">{item.title}</span><span className="block text-[9px] text-slate-400">{new Date(item.time).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}{item.score == null ? "" : ` · ${item.score}%`}</span></span>{item.type === "assessment" && <Eye size={12} className="text-plum"/>}</button>)}{!selectedEvents.length && !selectedActivity?.activities?.length && <p className="py-2 text-center text-[10px] text-slate-400">No activity or plans on this date.</p>}</div></div>{browserAlerts === "default" && <button onClick={enableNotifications} className="mt-2 flex w-full items-center justify-center gap-1 rounded-lg bg-sky/35 py-2 text-[10px] font-bold text-plum"><Bell size={12}/> Enable browser notifications</button>}</section>;
}

function ActivityIcon({ type }) {
  const styles = type === "assessment" ? "bg-mint text-emerald-700" : type === "material" ? "bg-peach text-amber-700" : "bg-sky text-blue-700";
  const Icon = type === "assessment" ? BookOpenCheck : type === "material" ? Upload : MessageSquareText;
  return <span className={`grid h-6 w-6 shrink-0 place-items-center rounded-md ${styles}`}><Icon size={12}/></span>;
}

function AssessmentHistory({ assessments, api, openReport }) {
  return <section className="glass-card p-4"><p className="eyebrow">Saved reports</p><h2 className="mt-1 text-base font-bold">Assessment history</h2><div className="mt-3 max-h-64 space-y-2 overflow-y-auto">{assessments.length ? assessments.map(item => <div key={item.id} className="rounded-lg bg-slate-50 p-2.5"><div className="flex items-center justify-between gap-3"><div className="min-w-0"><p className="truncate text-xs font-semibold">{item.title}</p><p className="mt-0.5 text-[10px] text-slate-500">{new Date(item.completed_at || item.created_at).toLocaleString()}</p></div><div className="flex items-center gap-1.5"><b className={`text-xs ${item.score < 50 ? "text-rose-600" : item.score < 70 ? "text-amber-600" : "text-emerald-700"}`}>{item.score}%</b><button title="View report" onClick={() => openReport(item.id)} className="icon-button h-8 w-8"><Eye size={14}/></button><DownloadMenu compact label="Download report" href={`${api}/api/assessments/${item.id}/download`}/></div></div></div>) : <p className="rounded-xl bg-slate-50 p-3 text-xs text-slate-500">Completed assessments will be stored here.</p>}</div></section>;
}

function RevisionPlan({ plan, setPage }) {
  return <section className="glass-card bg-gradient-to-r from-peach/45 to-mint/35 p-4"><p className="eyebrow">Personalised next steps</p><h2 className="mt-1 text-base font-bold">Weak-topic revision plan</h2>{plan.length ? <div className="mt-3 max-h-64 space-y-2 overflow-y-auto">{plan.map(item => <article key={item.topic} className="rounded-xl bg-white/80 p-3"><div className="flex items-start justify-between gap-3"><h3 className="text-sm font-bold">{item.topic}</h3><span className={`rounded-full px-2 py-0.5 text-[9px] font-bold uppercase ${item.priority === "urgent" ? "bg-rose-100 text-rose-700" : "bg-amber-100 text-amber-700"}`}>{item.priority}</span></div><p className="mt-1 text-[11px] leading-5 text-slate-600">Mastery {Math.round(item.mastery * 100)}%. {item.action}</p><div className="mt-2 flex gap-3"><button onClick={() => setPage("Learn")} className="text-[11px] font-bold text-plum">Learn →</button><button onClick={() => setPage("Practise")} className="text-[11px] font-bold text-emerald-700">Focused quiz →</button></div></article>)}</div> : <p className="mt-3 text-xs text-slate-600">Submit an assessment to create a targeted plan.</p>}</section>;
}

function ReportDetails({ api, assessment }) {
  const report = assessment.report;
  return <section className="space-y-4"><div className="glass-card bg-gradient-to-r from-lilac/60 to-mint/50 p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="eyebrow">Saved report</p><h2 className="mt-1 text-xl font-bold">{assessment.title}</h2><p className="mt-1 text-sm text-slate-600">{report.percentage}% · {report.correct_questions} of {report.total_questions} correct</p></div><DownloadMenu label="Download report" href={`${api}/api/assessments/${assessment.id}/download`}/></div>{report.weak_topics?.length > 0 && <div className="mt-4 rounded-xl bg-white/75 p-3 text-sm"><b className="text-rose-700">Weak topics to revise:</b> {report.weak_topics.join(", ")}</div>}</div>{report.feedback.map((item, index) => <article key={item.question_id} className={`glass-card border-l-4 p-5 ${item.correct ? "border-l-emerald-400" : "border-l-rose-300"}`}><div className="flex items-center gap-2">{item.correct ? <CheckCircle2 className="text-emerald-600" size={19}/> : <XCircle className="text-rose-500" size={19}/>}<p className="font-bold">Question {index + 1} · {item.topic}</p></div><div className="mt-3"><RichStudyText text={item.prompt}/></div><div className="mt-3 grid gap-1 rounded-xl bg-slate-50 p-3 text-sm text-slate-600"><p><b>Your answer:</b> {item.response || "No answer"}</p><p><b>Correct answer:</b> {item.correct_answer}</p></div><div className="mt-3 rounded-xl bg-sky/35 p-4"><p className="mb-1 text-xs font-bold uppercase tracking-wide text-slate-500">Personal feedback</p><RichStudyText text={item.feedback}/></div><div className="mt-3 rounded-xl bg-mint/35 p-4"><p className="mb-1 text-xs font-bold uppercase tracking-wide text-slate-500">Worked explanation</p><RichStudyText text={item.explanation}/></div>{item.misconception && <p className="mt-2 text-sm text-rose-700"><b>Likely misconception:</b> {item.misconception}</p>}</article>)}</section>;
}

function Legend({ color, label, value }) { return <div className="flex items-center justify-between rounded-lg bg-slate-50 px-2 py-1.5 text-[10px]"><span className="flex items-center gap-1 font-semibold text-slate-600"><i className={`h-2 w-2 rounded-full ${color}`}/>{label}</span><b>{value}</b></div>; }
function EmptyChart({ eyebrow, title, text }) { return <section className="glass-card p-4"><p className="eyebrow">{eyebrow}</p><h2 className="mt-1 text-base font-bold">{title}</h2><p className="mt-3 rounded-xl bg-sky/35 p-3 text-xs text-slate-600">{text}</p></section>; }
