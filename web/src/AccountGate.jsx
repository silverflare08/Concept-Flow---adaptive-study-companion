import React, { useEffect, useState } from "react";
import ProfileSettings from "./ProfileSettings.jsx";
import WelcomePage from "./WelcomePage.jsx";
import { themeId } from "./appearance.js";
import { ArrowRight, BookOpen, Eye, EyeOff, Leaf, LogOut, X } from "lucide-react";

export default function AccountGate({ api, children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [signup, setSignup] = useState(false);
  const [busy, setBusy] = useState(false);
  const [profile, setProfile] = useState(false);
  useEffect(() => {
    document.documentElement.dataset.theme = themeId(user?.preferences?.theme);
    return () => { delete document.documentElement.dataset.theme; };
  }, [user?.preferences?.theme]);
  useEffect(() => {
    const sizes = { small: "14px", normal: "16px", large: "18px" };
    document.documentElement.style.fontSize = sizes[user?.preferences?.font_size] || "16px";
    return () => { document.documentElement.style.fontSize = ""; };
  }, [user?.preferences?.font_size]);
  async function request(path, options = {}) {
    const response = await window.fetch(`${api}/api/auth/${path}`, { credentials: "include", ...options });
    const data = await response.json();
    if (!response.ok) throw new Error(Array.isArray(data.detail) ? data.detail.map(item => item.msg).join("; ") : data.detail || "Request failed.");
    return data;
  }
  useEffect(() => {
    let active = true;
    window.fetch(`${api}/api/auth/me`, { credentials: "include" }).then(async response => {
      if (response.ok) { const data = await response.json(); if (active) setUser(data.user); }
      else if (response.status !== 401) throw new Error("Could not check your session. Please restart the API.");
    }).catch(e => { if (active) setError(e.message); }).finally(() => { if (active) setLoading(false); });
    const expired = () => { setUser(null); setProfile(false); setError("Your session ended. Please sign in again."); };
    window.addEventListener("conceptflow-session-expired", expired);
    return () => { active = false; window.removeEventListener("conceptflow-session-expired", expired); };
  }, [api]);
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError("");
    const fields = Object.fromEntries(new FormData(event.currentTarget));
    if (signup) fields.local_processing_consent = fields.local_processing_consent === "on";
    try { setUser((await request(signup ? "signup" : "login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(fields) })).user); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function logout(all = false) {
    try { await request(all ? "logout-all" : "logout", { method: "POST" }); setUser(null); setProfile(false); }
    catch (e) { setError(e.message); throw e; }
  }
  if (loading) return <main className="grid min-h-screen place-items-center bg-[#f8f7fc]"><p role="status" className="text-plum">Opening your study space…</p></main>;
  if (user) return <>{children({ user, openProfile: () => { setProfile(true); setError(""); } })}{profile && <ProfileSettings user={user} request={request} onUser={setUser} onClose={() => setProfile(false)} onLogout={logout} onPasswordChanged={() => { setUser(null); setProfile(false); setError("Password changed. Please sign in again."); }}/>}</>;
  return <WelcomePage><section id="signin" className="welcome-auth glass-card p-5 sm:p-6"><h2 className="text-2xl font-bold">{signup ? "Make room for learning" : "Welcome back"}</h2><p className="mt-2 text-sm text-slate-500">{signup ? "Create your own ConceptFlow account." : "Sign in to your personal study space."}</p><form onSubmit={submit} className="mt-4 space-y-3">{signup && <><Field name="name" label="Your name" autoComplete="name" maxLength={80}/><Field name="username" label="Username" autoComplete="username" minLength={3} maxLength={30} pattern="[a-zA-Z0-9][a-zA-Z0-9_-]{2,29}"/><Field name="email" label="Email" type="email" autoComplete="email" maxLength={254}/></>}{!signup && <Field name="identifier" label="Username or email" autoComplete="username"/>}<Field name="password" label="Password" type="password" autoComplete={signup ? "new-password" : "current-password"} minLength={signup ? 10 : 1} maxLength={128}/>{signup && <label className="flex items-start gap-2 text-xs leading-5 text-slate-600"><input name="local_processing_consent" type="checkbox" required className="mt-1"/>I agree to my study data being stored on this server and processed by the configured AI services. I will only upload material I may use.</label>}{error && <p role="alert" className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}<button disabled={busy} className="primary-button w-full justify-center disabled:opacity-50">{busy ? "Please wait…" : signup ? "Create account" : "Sign in"}<ArrowRight size={16}/></button></form><button onClick={() => { setSignup(!signup); setError(""); }} className="mt-4 text-sm font-medium text-plum">{signup ? "Already have an account? Sign in" : "New here? Create an account"}</button><p className="mt-3 text-xs leading-5 text-slate-400">Previously saved data is preserved separately. New accounts start with a fresh workspace; nothing is automatically assigned.</p></section></WelcomePage>;
}
function Field({ label, ...props }) {
  const [visible, setVisible] = useState(false);
  const isPassword = props.name === "password";
  const isUsername = props.name === "username";
  const isNewPassword = isPassword && props.autoComplete === "new-password";
  const id = `account-${props.name}`;
  const hint = isUsername ? "3–30 English letters or numbers; dots, underscores and hyphens allowed. Start with a letter or number. No spaces. Example: palak.mittal" : isNewPassword ? "10–128 characters. Choose a separate ConceptFlow password—not your Gmail password." : "";
  // HTML's Unicode-set pattern syntax requires escaping punctuation in character classes.
  const pattern = isUsername ? "[a-zA-Z0-9][a-zA-Z0-9_.\\-]{2,29}" : props.pattern;
  return <div className="text-sm font-medium">
    <label htmlFor={id}>{label}</label>
    <div className="mt-2 flex items-stretch gap-2">
      <input required {...props} id={id} pattern={pattern} type={isPassword && visible ? "text" : props.type} aria-describedby={hint ? `${id}-hint` : undefined} title={hint || undefined} className="min-w-0 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 outline-none focus:border-plum focus:ring-2 focus:ring-purple-100"/>
      {isPassword && <button type="button" aria-label={visible ? "Hide password" : "Show password"} aria-controls={id} aria-pressed={visible} onClick={() => setVisible(value => !value)} className="flex min-h-11 shrink-0 items-center justify-center gap-1.5 rounded-xl border border-purple-200 bg-purple-50 px-3 text-xs font-semibold text-plum hover:bg-purple-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-plum">
        {visible ? <EyeOff size={20} strokeWidth={2} aria-hidden="true"/> : <Eye size={20} strokeWidth={2} aria-hidden="true"/>}
        <span>{visible ? "Hide" : "Show"}</span>
      </button>}
    </div>
    {hint && <p id={`${id}-hint`} className="mt-1.5 text-xs font-normal leading-5 text-slate-500">{hint}</p>}
  </div>;
}
