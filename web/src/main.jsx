import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { ArrowRight, BarChart3, BookOpen, BrainCircuit, CheckCircle2, ChevronRight, CircleHelp, Clock3, FileText, FolderPlus, GitBranch, Home, Layers3, Leaf, Menu, MessageSquareText, Search, Sparkles, Target, Upload, X } from "lucide-react";
import "./index.css";
import StudyViews from "./StudyViews.jsx";
import MaterialsPage from "./MaterialsPage.jsx";
import HistoryPage from "./HistoryPage.jsx";
import TutorPage from "./TutorPage.jsx";
import DashboardPage from "./DashboardPage.jsx";
import AssessmentPage from "./AssessmentPage.jsx";
import ProgressPage from "./ProgressPage.jsx";

// In development, Vite forwards /api to FastAPI. This avoids browser-specific
// localhost restrictions; deployment can override it with VITE_API_URL.
const API = import.meta.env.VITE_API_URL || "";
const navItems = [["Home", Home], ["Learn", BookOpen], ["Learning Flow", BookOpen], ["Revision Mind Map", GitBranch], ["Practise", Target], ["Progress", BarChart3], ["Materials", Layers3], ["History", Clock3]];

function App() {
  const [page, setPage] = useState("Home");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [workspace, setWorkspace] = useState({ name: "My study space", source_count: 0, chunk_count: 0, sources: [] });
  const [courseMap, setCourseMap] = useState(null);
  const [guideProgress, setGuideProgress] = useState(null);
  const [query, setQuery] = useState("");
  const [tutorState, setTutorState] = useState({ status: "idle", reply: null, message: "" });
  const [notice, setNotice] = useState("");
  const [library, setLibrary] = useState({ courses: [], conversations: [], artifacts: [], assessments: [] });
  const [conversationId, setConversationId] = useState(null);
  const [selectedConversationId, setSelectedConversationId] = useState(null);

  async function refreshLibrary() {
    const [coursesResponse, historyResponse] = await Promise.all([fetch(`${API}/api/courses`), fetch(`${API}/api/history`)]);
    if (coursesResponse.ok && historyResponse.ok) {
      const courses = await coursesResponse.json(); const history = await historyResponse.json();
      setLibrary({ courses: courses.courses, conversations: history.conversations, artifacts: history.artifacts, assessments: history.assessments || [] });
    }
  }

  async function refreshWorkspace() {
    try { const response = await fetch(`${API}/api/workspace`); if (response.ok) { const data = await response.json(); setWorkspace(data); const mapResponse = await fetch(`${API}/api/course-map`); if (mapResponse.ok) setCourseMap((await mapResponse.json()).course_map); await refreshLibrary(); setNotice(""); } }
    catch { setNotice("The frontend is running, but the Python API is not connected yet. Start it with uvicorn."); }
  }
  useEffect(() => { refreshWorkspace(); }, []);

  async function createWorkspace(name) {
    const response = await fetch(`${API}/api/workspace`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) });
    if (!response.ok) throw new Error("Could not create course workspace.");
    const data = await response.json(); setWorkspace(data); setCourseMap(null); setGuideProgress(null); setConversationId(null); await refreshLibrary(); setNotice(`Created “${data.name}”. Add materials to begin.`); return data;
  }
  async function uploadMaterials(files) {
    const form = new FormData(); Array.from(files).forEach(file => form.append("files", file));
    const response = await fetch(`${API}/api/materials`, { method: "POST", body: form });
    const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Upload failed.");
    setWorkspace(data.workspace); setCourseMap(null); await refreshLibrary(); setNotice(data.reports.map(report => report.message || `${report.name}: ${report.status} (${report.chunks || 0} chunks)`).join(" · "));
  }
  async function uploadUrl(url) {
    const response = await fetch(`${API}/api/materials/url`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url }) });
    const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Link import failed.");
    setWorkspace(data.workspace); setCourseMap(null); await refreshLibrary(); setNotice(`${data.report.name}: indexed (${data.report.chunks} chunks)`); return data;
  }
  async function deleteMaterial(sourceId) {
    const response = await fetch(`${API}/api/materials/${sourceId}`, { method: "DELETE" });
    const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Could not delete this material.");
    setWorkspace(data.workspace); setCourseMap(null); setGuideProgress(null); await refreshLibrary();
    setNotice(`Deleted “${data.deleted.name}” from ${data.workspace.name}.`); return data;
  }
  async function askTutor() {
    if (!query.trim()) return; setTutorState({ status: "loading", reply: null, message: "" });
    try {
      const response = await fetch(`${API}/api/tutor`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: query, conversation_id: conversationId }) });
      const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Tutor request failed.");
      setConversationId(data.conversation_id); setTutorState({ status: data.coverage === "not_covered" ? "empty" : "ready", reply: data, message: data.coverage === "not_covered" ? data.answer : "" }); await refreshLibrary();
    } catch (error) { setTutorState({ status: "error", reply: null, message: error.message }); }
  }
  async function generateCourseMap(view, sourceIds = []) {
    setGuideProgress({ status: "running", view, completed_batches: 0, total_batches: 0 });
    try {
      const response = await fetch(`${API}/api/study-guide/generate`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source_ids: sourceIds }) });
      const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Could not prepare your study views.");
      let job = data.job;
      while (job?.status === "running") {
        setGuideProgress({ ...job, view });
        await new Promise(resolve => setTimeout(resolve, 1500));
        const statusResponse = await fetch(`${API}/api/study-guide/status`);
        if (!statusResponse.ok) throw new Error("Could not check study guide progress.");
        const status = await statusResponse.json();
        if (status.job?.job_id !== data.job.job_id) throw new Error("Material changed. Generate study views again.");
        job = status.job;
      }
      if (job?.status !== "complete") throw new Error(job?.error || "Material changed. Generate study views again.");
      const mapResponse = await fetch(`${API}/api/course-map`);
      if (!mapResponse.ok) throw new Error("Could not load your study views.");
      const result = await mapResponse.json(); setCourseMap(result.course_map); setGuideProgress({ ...job, view });
      setWorkspace(current => ({ ...current, course_map_ready: true })); await refreshLibrary(); return result.course_map;
    } catch (error) { setGuideProgress({ status: "failed", view, error: error.message }); throw error; }
  }
  function startTutorFor(conceptName) {
    setTutorState({ status: "idle", reply: null, message: "" });
    setQuery(`Teach me ${conceptName} in simple words, using my course material.`);
    setPage("Learn");
  }
  async function selectCourse(courseId, destination = "Home") {
    const response = await fetch(`${API}/api/courses/${courseId}/activate`, { method: "POST" });
    const data = await response.json(); if (!response.ok) throw new Error(data.detail || "Could not open that course.");
    setWorkspace(data); setConversationId(null); setTutorState({ status: "idle", reply: null, message: "" });
    const mapResponse = await fetch(`${API}/api/course-map`); if (mapResponse.ok) setCourseMap((await mapResponse.json()).course_map);
    await refreshLibrary(); setNotice(`Opened “${data.name}”.`); setPage(destination);
  }
  function openHistoryConversation(id) { setSelectedConversationId(id); setPage("History"); setSidebarOpen(false); }
  function newChat() { setConversationId(null); setQuery(""); setTutorState({ status: "idle", reply: null, message: "" }); }

  const content = {
    Home: <DashboardPage workspace={workspace} setPage={setPage} notice={notice} />,
    Learn: <TutorPage api={API} workspace={workspace} query={query} setQuery={setQuery} askTutor={askTutor} state={tutorState} conversationId={conversationId} newChat={newChat} />,
    "Learning Flow": <StudyViews mode="learning" workspace={workspace} guide={courseMap} generate={generateCourseMap} progress={guideProgress} setPage={setPage} startTutorFor={startTutorFor} api={API}/>,
    "Revision Mind Map": <StudyViews mode="revision" workspace={workspace} guide={courseMap} generate={generateCourseMap} progress={guideProgress} setPage={setPage} startTutorFor={startTutorFor} api={API}/>,
    Practise: <AssessmentPage api={API} workspace={workspace} guide={courseMap} refreshLibrary={refreshLibrary} />,
    Progress: <ProgressPage api={API} workspace={workspace} setPage={setPage} />,
    Materials: <MaterialsPage api={API} workspace={workspace} courses={library.courses} createWorkspace={createWorkspace} selectCourse={courseId => selectCourse(courseId, "Materials")} uploadMaterials={uploadMaterials} uploadUrl={uploadUrl} deleteMaterial={deleteMaterial} notice={notice} />,
    History: <HistoryPage api={API} history={{ conversations: library.conversations, artifacts: library.artifacts, assessments: library.assessments || [] }} courses={library.courses} activeCourseId={workspace.id} selectCourse={selectCourse} selectedConversationId={selectedConversationId} onSelectConversation={setSelectedConversationId} />
  };
  return <div className="min-h-screen bg-[radial-gradient(circle_at_88%_7%,#efeaff_0,transparent_25%),radial-gradient(circle_at_8%_88%,#e4f5ee_0,transparent_26%),#f8f7fc]">
    <aside className={`fixed inset-y-0 z-30 w-72 border-r border-white/70 bg-[#f3f0fa]/90 p-5 backdrop-blur-xl transition-transform lg:translate-x-0 ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}`}>
      <div className="mb-10 flex items-center justify-between"><Brand/><button onClick={() => setSidebarOpen(false)} className="lg:hidden"><X size={20}/></button></div>
      <p className="eyebrow mb-3 px-3">Workspace</p><nav className="space-y-1">{navItems.map(([label, Icon]) => <button key={label} onClick={() => { setPage(label); setSidebarOpen(false); }} className={`nav-item ${page === label ? "nav-item-active" : ""}`}><Icon size={18}/>{label}</button>)}</nav>
      <div className="mt-7 border-t border-white/70 pt-5"><p className="eyebrow mb-2 px-3">Recent courses</p><div className="space-y-1">{library.courses.slice(0, 3).map(course => <button key={course.id} onClick={() => selectCourse(course.id)} className={`w-full truncate rounded-xl px-3 py-2 text-left text-sm ${course.id === workspace.id ? "bg-white font-bold text-plum shadow-sm" : "text-slate-600 hover:bg-white/60"}`}>{course.name}</button>)}</div><p className="eyebrow mb-2 mt-5 px-3">Recent chats</p><div className="space-y-1">{library.conversations.slice(0, 3).map(item => <button key={item.id} onClick={() => openHistoryConversation(item.id)} className="w-full truncate rounded-xl px-3 py-2 text-left text-sm text-slate-600 hover:bg-white/60">{item.title}</button>)}</div></div>
    </aside>
    <main className="min-h-screen lg:pl-72"><header className="flex items-center justify-between px-5 py-5 sm:px-9"><button onClick={() => setSidebarOpen(true)} className="rounded-xl bg-white p-2 text-slate-600 shadow-sm lg:hidden"><Menu size={20}/></button><div className="hidden lg:block"/><div className="flex items-center gap-3"><div className="hidden text-right sm:block"><p className="text-sm font-semibold">{workspace.name}</p><p className="text-xs text-slate-500">{workspace.source_count} source{workspace.source_count === 1 ? "" : "s"} indexed</p></div><div className="grid h-10 w-10 place-items-center rounded-full bg-lilac font-bold text-plum">P</div></div></header><section className="mx-auto max-w-7xl px-5 pb-12 sm:px-9">{content[page]}</section></main>
  </div>;
}

function Brand() { return <div className="flex items-center gap-3"><div className="grid h-10 w-10 place-items-center rounded-2xl bg-plum text-white shadow-lg shadow-plum/25"><BrainCircuit size={22}/></div><div><p className="text-lg font-extrabold tracking-tight">ConceptFlow</p><p className="text-xs text-slate-500">Study with clarity</p></div></div>; }
function EmptyState({ icon, title, body, action }) { return <div className="glass-card border-dashed p-8 text-center"><div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-lilac text-plum">{icon}</div><h2 className="mt-4 text-lg font-bold">{title}</h2><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-600">{body}</p>{action && <div className="mt-5">{action}</div>}</div>; }

function Dashboard({ workspace, setPage, notice }) { const hasSources = workspace.source_count > 0; return <div className="space-y-7"><div className="glass-card overflow-hidden p-7 sm:p-10"><div className="grid items-center gap-8 lg:grid-cols-[1.3fr_.7fr]"><div><p className="eyebrow">Your learning space</p><h1 className="mt-3 max-w-xl text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl">Study any subject with <span className="text-plum">clarity.</span></h1><p className="mt-4 max-w-xl leading-7 text-slate-600">Create a focused course workspace from your own videos, PDFs, and slide decks. Every answer will be tied to your study material.</p><div className="mt-7 flex flex-wrap gap-3"><button onClick={() => setPage("Materials")} className="primary-button"><FolderPlus size={17}/> Create a course</button>{hasSources && <button onClick={() => setPage("Learn")} className="secondary-button">Ask your material <ArrowRight size={17}/></button>}</div></div><div className="rounded-3xl bg-gradient-to-br from-lilac to-mint p-6"><div className="mx-auto grid aspect-square max-w-[250px] place-items-center rounded-full border-[14px] border-white/70 bg-white/60 text-center"><div><p className="text-5xl font-extrabold text-plum">{workspace.chunk_count}</p><p className="mt-1 text-sm font-medium text-slate-600">searchable chunks</p><div className="mt-4 inline-flex items-center gap-1 rounded-full bg-mint px-3 py-1 text-xs font-semibold text-emerald-700"><Sparkles size={13}/> Your course, your evidence</div></div></div></div></div></div>{notice && <div className="rounded-2xl bg-sky/70 p-4 text-sm text-slate-700">{notice}</div>}<div className="grid gap-5 md:grid-cols-3"><Metric icon={<Layers3/>} label="Sources indexed" value={workspace.source_count} detail="PDF, slides, and video" color="sky"/><Metric icon={<MessageSquareText/>} label="Ask with evidence" value={hasSources ? "Ready" : "Waiting"} detail={hasSources ? "Search your material" : "Add your first source"} color="mint"/><Metric icon={<Target/>} label="Adaptive practice" value="Next" detail="After concept extraction" color="peach"/></div><section className="grid gap-6 lg:grid-cols-[1.2fr_.8fr]"><div className="glass-card p-6"><p className="eyebrow">How ConceptFlow works</p><h2 className="mt-2 text-xl font-bold">A workspace for every course</h2><div className="mt-5 grid gap-3 sm:grid-cols-3"><Step number="01" title="Add material" text="Upload your own course files."/><Step number="02" title="Find evidence" text="Search with precise citations."/><Step number="03" title="Learn adaptively" text="Practise weak concepts next."/></div></div><div className="glass-card bg-peach/50 p-6"><p className="eyebrow">Built transparently</p><h2 className="mt-2 text-xl font-bold">No invented course knowledge</h2><p className="mt-3 text-sm leading-6 text-slate-600">If your material does not contain the answer, ConceptFlow tells you instead of guessing.</p></div></section></div>; }
function Metric({ icon, label, value, detail, color }) { const colors = { sky: "bg-sky/45", mint: "bg-mint/45", peach: "bg-peach/45" }; return <div className={`glass-card ${colors[color]} p-5`}><div className="mb-4 inline-flex rounded-xl bg-white p-2 text-plum shadow-sm">{icon}</div><p className="text-sm text-slate-500">{label}</p><p className="mt-1 text-xl font-extrabold">{value}</p><p className="mt-1 text-xs text-slate-500">{detail}</p></div>; }
function Step({ number, title, text }) { return <div className="rounded-2xl bg-slate-50 p-4"><p className="text-xs font-black text-plum">{number}</p><p className="mt-2 font-bold">{title}</p><p className="mt-1 text-xs leading-5 text-slate-500">{text}</p></div>; }

function Learn({ workspace, query, setQuery, askTutor, state }) { if (!workspace.source_count) return <div className="space-y-6"><Title eyebrow="Evidence-first tutoring" title="Ask about your course" body="Tutoring begins once you add your own study material. ConceptFlow will teach only from that course workspace."/><EmptyState icon={<FolderPlus size={24}/>} title="Your workspace is empty" body="Upload a PDF or slide deck first, then ask questions in any subject—from biology and law to machine learning and literature."/></div>; return <div className="mx-auto max-w-4xl space-y-6"><Title eyebrow="Evidence-first tutoring" title="Learn with your course material" body="ConceptFlow retrieves your material before teaching. It clearly says when the course does not cover a question."/><div className="glass-card p-3"><div className="flex flex-col gap-3 sm:flex-row"><div className="relative flex-1"><MessageSquareText className="absolute left-4 top-3.5 text-slate-400" size={19}/><input value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => e.key === "Enter" && askTutor()} className="w-full rounded-xl border border-slate-200 bg-white py-3 pl-11 pr-4 outline-none transition focus:border-plum" placeholder="For example: Explain this topic in simple words"/></div><button onClick={askTutor} className="primary-button justify-center">{state.status === "loading" ? "Teaching…" : "Ask tutor"}<ArrowRight size={17}/></button></div></div>{state.reply && state.status === "ready" && <TutorCard reply={state.reply}/>} {state.status === "empty" && <EmptyState icon={<CircleHelp size={24}/>} title="Not covered by your material" body={state.message}/>} {state.status === "error" && <div className="rounded-2xl bg-peach p-5 text-sm text-slate-700"><b>Tutor unavailable:</b> {state.message}<p className="mt-2">Make sure Ollama is running and the qwen2.5:3b-instruct model is installed.</p></div>}</div>; }
function TutorCard({ reply }) { return <div className="glass-card border-l-4 border-l-plum p-6"><div className="mb-4 flex flex-wrap items-center gap-3"><span className="inline-flex items-center gap-2 rounded-full bg-mint px-3 py-1 text-xs font-bold text-emerald-700"><CheckCircle2 size={14}/> Course-backed explanation</span><span className="text-xs text-slate-500">Sources are verified by ConceptFlow</span></div><p className="whitespace-pre-wrap text-lg leading-8 text-slate-700">{reply.answer}</p><div className="mt-5"><p className="text-xs font-bold uppercase tracking-[.14em] text-slate-500">Why this answer is supported</p><div className="mt-3 grid gap-3">{reply.citations.map(citation => <div key={citation.label} className="rounded-2xl bg-sky/35 p-4"><p className="font-bold text-slate-700">From {citation.source_name} · {citation.page ? `PDF page ${citation.page}` : citation.slide ? `Slide ${citation.slide}` : citation.label}</p><p className="mt-2 text-sm leading-6 text-slate-600">“{citation.excerpt}”</p></div>)}</div></div><div className="mt-5 rounded-2xl bg-lilac/50 p-4 text-sm text-slate-700"><b>Next step:</b> {reply.follow_up}</div></div>; }
function Title({ eyebrow, title, body }) { return <div><p className="eyebrow">{eyebrow}</p><h1 className="mt-2 text-3xl font-extrabold">{title}</h1><p className="mt-2 max-w-2xl text-slate-600">{body}</p></div>; }

function Practise({ workspace, setPage }) { return <div className="space-y-6"><Title eyebrow="Adaptive assessment" title="Practise what matters next" body="Assessment generation will be based on the concepts and prerequisites extracted from your uploaded course, not a fixed DSA quiz."/>{workspace.source_count ? <EmptyState icon={<BrainCircuit size={24}/>} title="Assessment generation is the next AI milestone" body="Your material is indexed. Next we will use its concepts and cited evidence to generate, validate, and adapt questions for this specific course."/> : <EmptyState icon={<FolderPlus size={24}/>} title="Add course material first" body="Upload a PDF or slide deck before creating a source-grounded assessment." action={<button onClick={() => setPage("Materials")} className="primary-button">Add materials <ArrowRight size={17}/></button>}/>}</div>; }
function Progress({ workspace, setPage }) { return <div className="space-y-6"><Title eyebrow="Your learning journey" title="Progress with purpose" body="Concept mastery appears here after ConceptFlow extracts the course structure and you complete assessments."/>{workspace.source_count ? <div className="glass-card p-7"><p className="eyebrow">Current course</p><h2 className="mt-2 text-2xl font-bold">{workspace.name}</h2><p className="mt-3 text-slate-600">{workspace.chunk_count} cited chunks are ready for concept tagging and the learner model.</p><div className="mt-6 rounded-2xl bg-mint p-5 text-sm text-slate-700"><b>Next:</b> extract topics and prerequisites, then initialise a diagnostic assessment.</div></div> : <EmptyState icon={<BarChart3 size={24}/>} title="Your progress will grow here" body="Start by adding a course workspace. Progress is always tied to the subject you are actually studying." action={<button onClick={() => setPage("Materials")} className="primary-button">Create course <ArrowRight size={17}/></button>}/>}</div>; }

function Materials({ workspace, createWorkspace, uploadMaterials, notice }) { const [name, setName] = useState(workspace.name); const [files, setFiles] = useState([]); const [busy, setBusy] = useState(false); const [error, setError] = useState(""); async function beginCourse() { try { setBusy(true); setError(""); await createWorkspace(name); } catch (e) { setError(e.message); } finally { setBusy(false); } } async function submitFiles() { if (!files.length) return; try { setBusy(true); setError(""); await uploadMaterials(files); setFiles([]); } catch (e) { setError(e.message); } finally { setBusy(false); } } return <div className="space-y-6"><Title eyebrow="Course workspace" title="Build a study space for any subject" body="Create a separate workspace for any course: data science, medicine, history, law, language learning, or anything else you study."/><div className="grid gap-6 lg:grid-cols-[.8fr_1.2fr]"><section className="glass-card p-6"><p className="text-sm font-bold">1. Name your course</p><input value={name} onChange={e => setName(e.target.value)} className="mt-3 w-full rounded-xl border border-slate-200 bg-white px-4 py-3 outline-none focus:border-plum" placeholder="e.g. Machine Learning - Unit 1"/><button disabled={busy || !name.trim()} onClick={beginCourse} className="primary-button mt-4 disabled:opacity-50">Create new workspace <ArrowRight size={17}/></button><p className="mt-3 text-xs leading-5 text-slate-500">Creating a workspace starts a fresh course, so material from another subject does not get mixed in.</p></section><section className="glass-card p-6"><p className="text-sm font-bold">2. Upload study material</p><label className="mt-3 block cursor-pointer rounded-2xl border-2 border-dashed border-lavender bg-lilac/20 p-8 text-center transition hover:bg-lilac/40"><input className="hidden" type="file" accept=".pdf,.pptx,.mp4,.mov,.mkv" multiple onChange={e => setFiles(Array.from(e.target.files || []))}/><div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-white text-plum shadow-sm"><Upload size={22}/></div><p className="mt-3 font-bold">Choose PDFs, slides, or videos</p><p className="mt-1 text-xs text-slate-500">PDF and PPTX indexing work now. Video transcription is next.</p></label>{files.length > 0 && <div className="mt-4 space-y-2">{files.map(file => <div key={`${file.name}-${file.size}`} className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2 text-sm"><span className="truncate font-medium">{file.name}</span><span className="ml-3 text-xs text-slate-500">{Math.ceil(file.size / 1024)} KB</span></div>)}<button disabled={busy} onClick={submitFiles} className="primary-button mt-2">{busy ? "Processing…" : "Upload and index"} <Upload size={17}/></button></div>}</section></div>{error && <div className="rounded-2xl bg-peach p-4 text-sm text-slate-700">{error}</div>}{notice && <div className="rounded-2xl bg-sky/70 p-4 text-sm text-slate-700">{notice}</div>}{workspace.sources.length > 0 && <section className="glass-card p-6"><div className="flex items-center justify-between"><div><p className="eyebrow">Active course</p><h2 className="mt-1 text-xl font-bold">{workspace.name}</h2></div><span className="rounded-full bg-mint px-3 py-1 text-sm font-bold text-emerald-700">{workspace.chunk_count} chunks</span></div><div className="mt-5 space-y-3">{workspace.sources.map((source, index) => <div key={`${source.name}-${index}`} className="flex items-center justify-between rounded-xl bg-slate-50 p-4"><div className="flex items-center gap-3"><FileText className="text-plum" size={19}/><div><p className="font-semibold">{source.name}</p><p className="text-xs text-slate-500">{source.type?.toUpperCase()} · {source.chunks || 0} chunks</p></div></div><span className={`rounded-full px-3 py-1 text-xs font-bold ${source.status === "indexed" ? "bg-mint text-emerald-700" : "bg-peach text-amber-700"}`}>{source.status}</span></div>)}</div></section>}</div>; }

createRoot(document.getElementById("root")).render(<App />);
