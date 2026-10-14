import React from "react";
import { BellRing, CalendarDays, Check, X } from "lucide-react";

export default function ReminderCentre({ reminders, onComplete, onDismiss, onOpenPlanner }) {
  if (!reminders.length) return null;
  async function enableBrowserAlerts() {
    if ("Notification" in window && Notification.permission === "default") await Notification.requestPermission();
  }
  return <aside className="fixed right-4 top-4 z-40 w-[min(23rem,calc(100vw-2rem))] space-y-2" aria-label="Due study reminders">
    {reminders.slice(0, 3).map(reminder => <section key={reminder.id} className="rounded-2xl border border-white bg-[#fbfaff]/95 p-4 shadow-xl backdrop-blur">
      <div className="flex items-start gap-3"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-peach text-rose-600"><BellRing size={17}/></span><div className="min-w-0 flex-1"><div className="flex items-start justify-between gap-2"><div><p className="text-[10px] font-black uppercase tracking-[.14em] text-rose-500">Study reminder</p><p className="mt-1 truncate text-sm font-extrabold text-slate-800">{reminder.title}</p></div><button onClick={() => onDismiss(reminder.id)} aria-label="Hide reminder for this session" className="text-slate-400 hover:text-slate-700"><X size={16}/></button></div><p className="mt-1 text-xs text-slate-500">{reminder.course_name} · {new Date(reminder.scheduled_for).toLocaleString()}</p><div className="mt-3 flex flex-wrap gap-2"><button onClick={() => onComplete(reminder)} className="inline-flex items-center gap-1 rounded-lg bg-mint px-2.5 py-1.5 text-xs font-bold text-emerald-800"><Check size={13}/> Mark done</button><button onClick={onOpenPlanner} className="inline-flex items-center gap-1 rounded-lg bg-lilac px-2.5 py-1.5 text-xs font-bold text-plum"><CalendarDays size={13}/> Open planner</button>{"Notification" in window && Notification.permission === "default" && <button onClick={enableBrowserAlerts} className="px-2 py-1.5 text-xs font-bold text-slate-500">Enable browser alerts</button>}</div></div></div>
    </section>)}
  </aside>;
}
