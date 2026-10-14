import React, { useEffect, useState } from "react";
import { BookOpen, CheckCircle2, Download, Eye, FileArchive, FileQuestion, MessageSquareText, XCircle } from "lucide-react";
import WorkingState from "./WorkingState.jsx";
import DownloadMenu from "./DownloadMenu.jsx";
import RichStudyText from "./RichStudyText.jsx";

function dateLabel(value) {
  if (!value) return "";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export default function HistoryPage({ api, history, courses, activeCourseId, selectCourse, selectedConversationId, onSelectConversation }) {
  const [conversation, setConversation] = useState(null);
  const [assessment, setAssessment] = useState(null);
  const [openingAssessment, setOpeningAssessment] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!selectedConversationId) { setConversation(null); return; }
    fetch(`${api}/api/conversations/${selectedConversationId}`)
      .then(response => response.ok ? response.json() : Promise.reject(new Error("Could not open that conversation.")))
      .then(setConversation)
      .catch(error => setError(error.message));
  }, [api, selectedConversationId, history]);

  async function openAssessment(id) {
    setOpeningAssessment(true); setError("");
    try {
      const response = await fetch(`${api}/api/assessments/${id}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not open that assessment.");
      setAssessment(data);
    } catch (issue) { setError(issue.message); } finally { setOpeningAssessment(false); }
  }

  return <div className="space-y-6">
    <div><p className="eyebrow">Your saved work</p><h1 className="mt-1 text-2xl font-extrabold">Courses and history</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">Return to a course, review earlier prompts, or open saved assessment feedback without creating it again.</p></div>
    {error && <div className="rounded-2xl bg-peach p-4 text-sm text-slate-700">{error}</div>}
    <section className="glass-card p-6"><div className="flex items-center justify-between"><div><p className="eyebrow">Course library</p><h2 className="mt-1 text-xl font-bold">Your workspaces</h2></div><BookOpen className="text-plum"/></div><div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">{courses.map(course => <button key={course.id} onClick={() => selectCourse(course.id)} className={`rounded-2xl border p-4 text-left transition hover:-translate-y-0.5 hover:shadow-sm ${course.id === activeCourseId ? "border-plum bg-lilac/45" : "border-slate-100 bg-slate-50"}`}><p className="font-bold">{course.name}</p><p className="mt-2 text-xs text-slate-500">{course.source_count} materials · {course.chunk_count} searchable sections</p><p className="mt-1 text-xs text-slate-400">Updated {dateLabel(course.updated_at)}</p></button>)}</div></section>
    {history.archivedCourses?.length > 0 && <section className="glass-card p-5"><div className="flex items-center gap-2"><FileArchive className="text-plum"/><h2 className="text-lg font-bold">Archived workspaces</h2></div><p className="mt-1 text-xs text-slate-500">Removed from active study, but their chats, assessments, generated maps and source files are still preserved below.</p><div className="mt-3 flex flex-wrap gap-2">{history.archivedCourses.map(course => <span key={course.id} className="rounded-full bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-600">{course.name}</span>)}</div></section>}
    <div className="grid gap-6 lg:grid-cols-[.8fr_1.2fr]">
      <section className="glass-card p-6"><div className="flex items-center gap-2"><MessageSquareText className="text-plum"/><h2 className="text-xl font-bold">Chat history</h2></div><div className="mt-4 max-h-[38rem] space-y-2 overflow-y-auto overscroll-contain pr-2">{history.conversations.length ? history.conversations.map(item => <button key={item.id} onClick={() => onSelectConversation(item.id)} className={`w-full rounded-xl p-3 text-left ${selectedConversationId === item.id ? "bg-lilac" : "bg-slate-50 hover:bg-sky/40"}`}><p className="truncate text-sm font-semibold">{item.title}</p><p className="mt-1 text-xs text-slate-500">{item.course_name} · {dateLabel(item.updated_at)}</p></button>) : <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-500">Your tutor conversations will appear here.</p>}</div></section>
      <section className="glass-card p-6">{conversation ? <><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="eyebrow">Saved conversation</p><h2 className="mt-1 text-xl font-bold">{conversation.title}</h2></div><DownloadMenu label="Download chat" href={`${api}/api/conversations/${conversation.id}/download`}/></div><div className="mt-5 max-h-[42rem] space-y-4 overflow-y-auto pr-2">{conversation.messages.map(message => <div key={message.id} className={`rounded-2xl p-4 ${message.role === "user" ? "ml-8 bg-lilac/55" : "mr-8 bg-sky/40"}`}><div className="flex items-center justify-between gap-3"><p className="text-xs font-bold uppercase tracking-wide text-plum">{message.role === "user" ? "You" : "ConceptFlow"}</p><time className="text-[10px] text-slate-400">{dateLabel(message.created_at)}</time></div><div className="mt-2">{message.role === "assistant" ? <RichStudyText text={message.content}/> : <p className="whitespace-pre-wrap leading-7 text-slate-700">{message.content}</p>}</div>{message.metadata?.citations?.length > 0 && <div className="mt-3 border-t border-white/70 pt-3 text-xs text-slate-500">{message.metadata.citations.map((citation, index) => <p key={index}>Source: {citation.label}</p>)}</div>}</div>)}</div></> : <div className="grid min-h-64 place-items-center text-center"><div><MessageSquareText className="mx-auto text-plum" size={30}/><p className="mt-3 font-bold">Select a previous conversation</p><p className="mt-1 text-sm text-slate-500">The complete question, answer and cited sources will appear here.</p></div></div>}</section>
    </div>
    <section className="glass-card p-5"><div className="flex items-center gap-2"><FileQuestion className="text-plum"/><h2 className="text-lg font-bold">Assessment history</h2></div><div className="mt-4 grid gap-3 md:grid-cols-2">{history.assessments?.length ? history.assessments.map(item => <div key={item.id} className="flex items-center justify-between gap-4 rounded-xl bg-slate-50 p-3"><div className="min-w-0"><p className="truncate text-sm font-semibold">{item.title}</p><p className="mt-1 text-xs text-slate-500">{item.course_name} · {item.status === "completed" ? `${item.score}%` : "Ready to take"}</p></div><div className="flex shrink-0 gap-2"><button title="Open assessment and mistakes" onClick={() => openAssessment(item.id)} className="icon-button"><Eye size={17}/></button><DownloadMenu compact label={item.status === "completed" ? "Download report" : "Download question paper"} href={`${api}/api/assessments/${item.id}/download`}/></div></div>) : <p className="text-sm text-slate-500">Completed quizzes and mock exams will appear here.</p>}</div></section>
    {openingAssessment && <WorkingState title="Opening your saved assessment" detail="Loading every answer, explanation and misconception from the report."/>}
    {assessment?.report && <section className="space-y-3"><div className="glass-card bg-lilac/45 p-5"><p className="eyebrow">Assessment report</p><h2 className="mt-1 text-xl font-bold">{assessment.title}</h2><p className="mt-1 text-sm text-slate-600">{assessment.report.percentage}% · {assessment.report.correct_questions} of {assessment.report.total_questions} correct</p></div>{assessment.report.feedback.map((item, index) => <article key={item.question_id} className={`glass-card border-l-4 p-5 ${item.correct ? "border-l-emerald-400" : "border-l-rose-300"}`}><div className="flex items-center gap-2">{item.correct ? <CheckCircle2 size={18} className="text-emerald-600"/> : <XCircle size={18} className="text-rose-500"/>}<p className="font-bold">Question {index + 1} · {item.topic}</p></div><p className="mt-2 text-sm font-semibold">{item.prompt}</p><p className="mt-3 text-sm text-slate-600"><b>Your answer:</b> {item.response || "No answer"}</p><p className="mt-1 text-sm text-slate-600"><b>Correct answer:</b> {item.correct_answer}</p><p className="mt-3 rounded-xl bg-sky/35 p-3 text-sm leading-6 text-slate-700">{item.feedback}</p>{item.misconception && <p className="mt-2 text-sm text-rose-700"><b>Likely misconception:</b> {item.misconception}</p>}</article>)}</section>}
    <section className="glass-card p-6"><div className="flex items-center gap-2"><FileArchive className="text-plum"/><h2 className="text-xl font-bold">Generated downloads</h2></div><div className="mt-4 grid gap-3 md:grid-cols-2">{history.artifacts.length ? history.artifacts.map(item => <div key={item.id} className="flex items-center justify-between gap-4 rounded-xl bg-slate-50 p-4"><div className="min-w-0"><p className="truncate font-semibold">{item.title}</p><p className="mt-1 text-xs text-slate-500">{item.course_name} · {dateLabel(item.created_at)}</p></div><DownloadMenu compact label="Download generated item" href={`${api}/api/artifacts/${item.id}/download`}/></div>) : <p className="text-sm text-slate-500">Generated learning flows and revision maps will be saved here.</p>}</div></section>
  </div>;
}
