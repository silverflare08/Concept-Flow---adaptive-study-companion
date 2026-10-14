import React from "react";
import { ArrowRight, BookOpen, Check, GitBranch, Target } from "lucide-react";
import Brand from "./Brand.jsx";

const FAQ = [
  ["Is this free to run?", "Local Ollama models need no API credits, but require a computer with enough memory. External providers may charge if you configure them."],
  ["Where is my material stored?", "Your accounts, files and saved work live on the machine running the Python server. Each account has a separate study database and upload folder."],
  ["Can I trust every explanation?", "Citations help you check an answer against the original material. AI and extraction can still make mistakes, especially with handwriting and maths."],
  ["Can I reset a forgotten password?", "Email verification and forgotten-password recovery are not available yet. Keep your password safe; this local version is not ready for unrestricted public hosting."],
];
export default function WelcomePage({ children }) {
  return <main className="welcome-page app-shell relative isolate min-h-screen text-ink">
    <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden" aria-hidden="true">
      <svg className="welcome-wave absolute left-0 top-0 h-[850px] w-full" viewBox="0 0 1440 850" preserveAspectRatio="none" focusable="false">
        <path d="M0 0H1440V210C1180 105 1080 370 820 300S250 90 0 245Z" fill="#e8eeea"/>
        <path d="M0 235C250 80 535 410 835 325S1145 120 1440 235" fill="none" stroke="#d3dfd8" strokeWidth="1.5"/>
        <path d="M1440 500C1140 420 1010 650 780 610S280 710 0 655V850H1440Z" fill="#eceee7" opacity=".6"/>
      </svg>
    </div>
    <header className="mx-auto flex max-w-6xl items-center justify-center border-b border-slate-200 px-5 py-4 sm:px-8 sm:py-5"><a href="#welcome" aria-label="ConceptFlow welcome"><Brand prominent/></a></header>
    <section id="welcome" className="mx-auto grid max-w-6xl items-center gap-6 px-5 pb-8 pt-4 sm:px-8 md:grid-cols-[1.05fr_1fr] lg:gap-10">
      <div className="welcome-intro space-y-4"><div><p className="eyebrow">Your own material. A clearer way to learn.</p><h1 className="mt-3 max-w-xl text-[2.75rem] font-extrabold leading-[1.08] tracking-tight text-ink sm:text-[3rem] lg:text-[3.5rem]">Less confusion.<br/>More clarity.</h1><p className="mt-3 max-w-lg text-base leading-7 text-slate-600">Turn your notes, books and lectures into knowledge you can use. Connect the ideas, understand the details, and practise at your own pace.</p></div>
        <div className="rounded-2xl border border-lavender/70 bg-lilac/25 p-4"><div className="flex items-center justify-between gap-3"><p className="font-heading text-sm font-bold">A connected study workspace</p><span className="text-[10px] uppercase tracking-widest text-slate-500">Illustrative preview</span></div><div className="mt-3 grid grid-cols-3 gap-2">{[[BookOpen,"Your sources","Notes & lectures"],[GitBranch,"Connected ideas","Maps & explanations"],[Target,"Focused practice","Recall & assessment"]].map(([Icon,title,detail],index) => <div key={title} className="rounded-xl border border-white/70 bg-white/75 p-3"><div className="flex items-center justify-between"><Icon size={20} className="text-plum"/><span className="text-[10px] text-slate-400">0{index+1}</span></div><h2 className="mt-2 text-xs font-bold sm:text-sm">{title}</h2><p className="mt-1 text-[11px] leading-5 text-slate-500">{detail}</p></div>)}</div><p className="mt-3 flex items-center gap-2 text-xs text-slate-600"><Check size={14} className="text-plum"/>Keep explanations connected to their original sources.</p></div>
      </div>
      <div className="min-w-0">{children}</div>
    </section>
    <section id="how-it-works" className="mx-auto max-w-6xl border-t border-slate-200 px-5 py-10 sm:px-8"><div className="grid gap-6 sm:grid-cols-3">{[["01","Bring your material","Upload documents, images or recordings into a subject workspace."],["02","Understand the connections","Ask questions, follow a learning flow or build a revision map."],["03","Practise and revisit","Use assessments and saved reports to decide what to revise next."]].map(([number,title,body]) => <div key={number}><span className="text-xs font-semibold text-plum">{number}</span><h2 className="mt-2 text-base font-bold">{title}</h2><p className="mt-2 text-sm leading-6 text-slate-500">{body}</p></div>)}</div></section>
    <section id="faq" className="mx-auto grid max-w-6xl gap-6 border-t border-slate-200 px-5 py-10 sm:px-8 md:grid-cols-[.65fr_1fr]"><div><p className="eyebrow">Before you begin</p><h2 className="mt-2 text-2xl font-bold">A few useful answers.</h2><p className="mt-3 text-sm leading-6 text-slate-500">A clear view of how ConceptFlow works—and its current limits.</p></div><div>{FAQ.map(([question,answer]) => <details key={question} className="border-b border-slate-200 py-4 first:pt-0"><summary className="cursor-pointer text-sm font-semibold">{question}</summary><p className="mt-3 text-sm leading-6 text-slate-600">{answer}</p></details>)}</div></section>
    <footer className="mx-auto flex max-w-6xl flex-wrap justify-between gap-3 px-5 pb-7 text-xs text-slate-400 sm:px-8"><span>ConceptFlow · Study with clarity</span><span>Your material. Your pace.</span></footer>
  </main>;
}
