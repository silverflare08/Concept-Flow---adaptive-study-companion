import React from "react";
import {
  ArrowRight, BarChart3, BookOpen, BrainCircuit, Clock3, FilePlus2,
  GitBranch, Headphones, Layers3, MessageSquareText, Sparkles, Target,
} from "lucide-react";

const TOOLS = [
  { page: "Learn", title: "Ask your tutor", detail: "Get a cited explanation from your material.", icon: MessageSquareText, tone: "bg-sky/55" },
  { page: "Learning Flow", title: "Learning Flow", detail: "See what to study first and what follows.", icon: BookOpen, tone: "bg-lilac/65" },
  { page: "Revision Mind Map", title: "Revision map", detail: "Review the complete course at a glance.", icon: GitBranch, tone: "bg-mint/55" },
  { page: "Flashcards", title: "Flashcards", detail: "Practise active recall from verified concepts.", icon: Layers3, tone: "bg-peach/55" },
  { page: "Practise", title: "Take a test", detail: "Quick quizzes, diagnostics and exam practice.", icon: Target, tone: "bg-[#e7f0ff]" },
  { page: "Audio & Video", title: "Listen and watch", detail: "Turn a source into a guided explanation.", icon: Headphones, tone: "bg-[#f4eafa]" },
  { page: "Progress", title: "Progress analytics", detail: "Explore scores, mastery and weak topics.", icon: BarChart3, tone: "bg-[#e7f7ef]" },
  { page: "History", title: "Saved work", detail: "Return to chats, reports and generated guides.", icon: Clock3, tone: "bg-[#fff0e8]" },
];

export default function DashboardPage({ workspace, setPage, notice }) {
  const hasMaterial = workspace.source_count > 0;
  const openTool = page => setPage(hasMaterial || ["Materials", "History"].includes(page) ? page : "Materials");

  return <div className="space-y-5">
    <section className="glass-card relative overflow-hidden p-6 sm:p-8">
      <div className="pointer-events-none absolute -right-16 -top-20 h-64 w-64 rounded-full bg-lilac/70 blur-3xl"/>
      <div className="pointer-events-none absolute -bottom-24 left-1/3 h-52 w-52 rounded-full bg-mint/60 blur-3xl"/>
      <div className="relative grid items-center gap-7 lg:grid-cols-[1.35fr_.65fr]">
        <div>
          <span className="inline-flex items-center gap-2 rounded-full bg-white/80 px-3 py-1.5 text-xs font-bold text-plum shadow-sm"><Sparkles size={14}/> Your calm study command centre</span>
          <h1 className="mt-4 max-w-2xl text-3xl font-black leading-tight tracking-tight text-slate-800 sm:text-4xl">What would you like to <span className="text-plum">understand today?</span></h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">Upload almost any study material, learn it with exact sources, practise in different formats, and watch your understanding grow over time.</p>
          <div className="mt-5 flex flex-wrap gap-3">
            <button onClick={() => setPage("Materials")} className="primary-button"><FilePlus2 size={17}/>{hasMaterial ? "Add material" : "Start a study space"}</button>
            {hasMaterial && <button onClick={() => setPage("Learn")} className="secondary-button"><BrainCircuit size={17}/>Continue learning<ArrowRight size={16}/></button>}
          </div>
        </div>
        <div className="rounded-3xl border border-white/80 bg-white/65 p-5 shadow-soft backdrop-blur">
          <p className="eyebrow">Active study space</p>
          <h2 className="mt-2 truncate text-xl font-extrabold text-slate-800">{workspace.name}</h2>
          <div className="mt-5 grid grid-cols-2 gap-3">
            <Stat value={workspace.source_count} label="study materials"/>
            <Stat value={workspace.course_map_ready ? "Ready" : hasMaterial ? "Create" : "Waiting"} label="learning map"/>
          </div>
          <button onClick={() => openTool(workspace.course_map_ready ? "Learning Flow" : "Materials")} className="mt-4 flex w-full items-center justify-between rounded-2xl bg-gradient-to-r from-lilac/80 to-mint/70 px-4 py-3 text-left text-sm font-bold text-slate-700"><span>{workspace.course_map_ready ? "Open your learning route" : hasMaterial ? "Build your learning route" : "Add your first material"}</span><ArrowRight size={16}/></button>
        </div>
      </div>
    </section>

    {notice && <div className="rounded-2xl border border-sky/70 bg-sky/60 p-4 text-sm text-slate-700">{notice}</div>}

    <section>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><p className="eyebrow">Everything in one place</p><h2 className="mt-1 text-xl font-extrabold">Your study toolkit</h2></div>
        {!hasMaterial && <p className="text-xs font-medium text-slate-500">Choose any tool and we’ll take you to Materials first.</p>}
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {TOOLS.map(({ page, title, detail, icon: Icon, tone }) => <button key={page} onClick={() => openTool(page)} className="group glass-card p-4 text-left transition hover:-translate-y-1 hover:border-lavender hover:shadow-lg">
          <div className={`grid h-10 w-10 place-items-center rounded-2xl ${tone} text-plum transition group-hover:scale-105`}><Icon size={19}/></div>
          <div className="mt-4 flex items-center justify-between gap-2"><h3 className="font-extrabold text-slate-800">{title}</h3><ArrowRight className="text-slate-300 transition group-hover:translate-x-1 group-hover:text-plum" size={16}/></div>
          <p className="mt-1 text-xs leading-5 text-slate-500">{detail}</p>
        </button>)}
      </div>
    </section>

    <section className="grid gap-4 lg:grid-cols-[1.2fr_.8fr]">
      <div className="glass-card p-5"><p className="eyebrow">Suggested journey</p><h2 className="mt-1 text-lg font-extrabold">A simple way to study smarter</h2><div className="mt-4 grid gap-3 sm:grid-cols-3"><Journey number="01" title="Understand" detail="Ask questions or study the complete material."/><Journey number="02" title="Recall" detail="Use flashcards and short focused quizzes."/><Journey number="03" title="Improve" detail="Follow mastery insights and revise weak areas."/></div></div>
      <button onClick={() => openTool("Progress")} className="glass-card bg-gradient-to-br from-peach/45 to-mint/45 p-5 text-left transition hover:-translate-y-0.5"><BarChart3 className="text-plum"/><p className="eyebrow mt-4">Personalised for you</p><h2 className="mt-1 text-lg font-extrabold">Your next best study action</h2><p className="mt-2 text-sm leading-6 text-slate-600">Open Progress to see developing topics, assessment trends and a focused revision plan.</p><span className="mt-4 inline-flex items-center gap-1 text-sm font-bold text-plum">View learning insights <ArrowRight size={15}/></span></button>
    </section>
  </div>;
}

function Stat({ value, label }) { return <div className="rounded-2xl bg-slate-50/90 p-3"><p className="text-xl font-black text-plum">{value}</p><p className="mt-0.5 text-[11px] font-medium text-slate-500">{label}</p></div>; }
function Journey({ number, title, detail }) { return <div className="rounded-2xl bg-slate-50 p-4"><span className="text-xs font-black text-plum">{number}</span><p className="mt-2 font-bold">{title}</p><p className="mt-1 text-xs leading-5 text-slate-500">{detail}</p></div>; }
