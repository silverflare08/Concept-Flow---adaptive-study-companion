import React, { useEffect, useState } from "react";
import { Bell, CalendarDays, LoaderCircle, Trash2, X } from "lucide-react";

function localInputValue(value) {
  const date = value ? new Date(value) : new Date();
  const shifted = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return shifted.toISOString().slice(0, 16);
}

export default function StudyPlannerDialog({ event, date, busy, onSave, onDelete, onClose }) {
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [kind, setKind] = useState("study");
  const [scheduledFor, setScheduledFor] = useState("");
  const [reminderEnabled, setReminderEnabled] = useState(true);
  const [reminderAt, setReminderAt] = useState("");

  useEffect(() => {
    const defaultDate = date ? new Date(`${date}T18:00:00`) : new Date();
    const scheduled = event?.scheduled_for ? new Date(event.scheduled_for) : defaultDate;
    const reminder = event?.reminder_at ? new Date(event.reminder_at) : new Date(scheduled.getTime() - 30 * 60_000);
    setTitle(event?.title || "");
    setNotes(event?.notes || "");
    setKind(event?.kind || "study");
    setScheduledFor(localInputValue(scheduled));
    setReminderEnabled(Boolean(event ? event.reminder_at : true));
    setReminderAt(localInputValue(reminder));
  }, [event, date]);

  useEffect(() => {
    function escape(event_) { if (event_.key === "Escape" && !busy) onClose(); }
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [busy, onClose]);

  function submit(e) {
    e.preventDefault();
    onSave({
      title: title.trim(), notes: notes.trim(), kind,
      scheduled_for: new Date(scheduledFor).toISOString(),
      reminder_at: reminderEnabled ? new Date(reminderAt).toISOString() : null,
    });
  }

  return <div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/30 p-4 backdrop-blur-sm" onMouseDown={e => e.target === e.currentTarget && !busy && onClose()}>
    <form onSubmit={submit} className="w-full max-w-lg rounded-3xl border border-white/80 bg-[#fbfaff] p-6 shadow-2xl">
      <div className="flex items-start justify-between gap-4"><div className="grid h-11 w-11 place-items-center rounded-2xl bg-lilac text-plum"><CalendarDays size={21}/></div><button type="button" onClick={onClose} disabled={busy} aria-label="Close study planner" className="icon-button"><X size={18}/></button></div>
      <p className="eyebrow mt-4">Study planner</p><h2 className="mt-1 text-xl font-extrabold">{event ? "Amend your plan" : "Add a study plan"}</h2>
      <label className="mt-5 block text-xs font-bold text-slate-600">Title<input required maxLength={160} value={title} onChange={e => setTitle(e.target.value)} placeholder="Revise probability chapter" className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-plum"/></label>
      <div className="mt-4 grid gap-3 sm:grid-cols-2"><label className="text-xs font-bold text-slate-600">Plan type<select value={kind} onChange={e => setKind(e.target.value)} className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none"><option value="study">Study session</option><option value="revision">Revision</option><option value="assessment">Practice test</option><option value="deadline">Deadline</option></select></label><label className="text-xs font-bold text-slate-600">Date and time<input required type="datetime-local" value={scheduledFor} onChange={e => setScheduledFor(e.target.value)} className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-plum"/></label></div>
      <label className="mt-4 block text-xs font-bold text-slate-600">Notes<textarea maxLength={2000} rows={3} value={notes} onChange={e => setNotes(e.target.value)} placeholder="What should you finish in this session?" className="mt-2 w-full resize-none rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-plum"/></label>
      <div className="mt-4 rounded-2xl bg-sky/30 p-3"><label className="flex cursor-pointer items-center gap-2 text-sm font-bold text-slate-700"><input type="checkbox" checked={reminderEnabled} onChange={e => setReminderEnabled(e.target.checked)} className="accent-[#71529a]"/><Bell size={16} className="text-plum"/> Remind me</label>{reminderEnabled && <input required type="datetime-local" value={reminderAt} onChange={e => setReminderAt(e.target.value)} className="mt-3 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-plum"/>}<p className="mt-2 text-[11px] leading-4 text-slate-500">Due reminders reappear when ConceptFlow is reopened until you mark them complete.</p></div>
      <div className="mt-6 flex items-center justify-between gap-3"><div>{event && <button type="button" disabled={busy} onClick={() => onDelete(event)} className="inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-sm font-bold text-rose-600 hover:bg-rose-50"><Trash2 size={15}/> Delete</button>}</div><div className="flex gap-2"><button type="button" disabled={busy} onClick={onClose} className="secondary-button">Cancel</button><button disabled={busy || !title.trim()} className="primary-button">{busy && <LoaderCircle className="animate-spin" size={16}/>} {event ? "Save changes" : "Add plan"}</button></div></div>
    </form>
  </div>;
}
