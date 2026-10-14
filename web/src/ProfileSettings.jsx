import React, { useEffect, useRef, useState } from "react";
import { Check, Eye, EyeOff, LogOut, Palette, Settings, ShieldCheck, UserRound, X } from "lucide-react";
import Avatar, { AVATARS, canonicalAvatarId } from "./Avatar.jsx";
import { THEMES, themeId, isDarkTheme } from "./appearance.js";

export default function ProfileSettings({ user, request, onUser, onClose, onLogout, onPasswordChanged }) {
  const [tab, setTab] = useState("Profile");
  const [chosenTheme, setChosenTheme] = useState(themeId(user.preferences?.theme));
  const [chosenAvatar, setChosenAvatar] = useState(canonicalAvatarId(user.preferences?.avatar));
  const latestTheme = useRef(themeId(user.preferences?.theme));
  latestTheme.current = themeId(user.preferences?.theme);
  useEffect(() => {
    if (tab !== "Appearance") return undefined;
    document.documentElement.dataset.theme = chosenTheme;
    return () => { document.documentElement.dataset.theme = latestTheme.current; };
  }, [tab, chosenTheme]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [sessions, setSessions] = useState([]);
  const [sessionError, setSessionError] = useState("");
  const dialog = useRef(null);
  const dialogBehavior = useRef({ busy, onClose });
  dialogBehavior.current = { busy, onClose };
  useEffect(() => {
    const previous = document.activeElement;
    dialog.current?.querySelector("button")?.focus();
    const oldOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    function keys(event) {
      if (event.key === "Escape" && !dialogBehavior.current.busy) dialogBehavior.current.onClose();
      if (event.key !== "Tab") return;
      const items = [...dialog.current.querySelectorAll('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href]')];
      const first = items[0], last = items.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
    document.addEventListener("keydown", keys);
    return () => { document.body.style.overflow = oldOverflow; document.removeEventListener("keydown", keys); previous?.focus(); };
  }, []);
  useEffect(() => {
    let active = true;
    if (tab === "Security") request("sessions").then(data => { if (active) setSessions(data.sessions); }).catch(e => { if (active) setSessionError(e.message); });
    return () => { active = false; };
  }, [tab]);
  async function save(event) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    const fields = Object.fromEntries(new FormData(event.currentTarget));
    try {
      const preferences = { ...user.preferences };
      if (tab === "Settings" || tab === "Appearance") Object.assign(preferences, fields);
      if (tab === "Profile") preferences.avatar = chosenAvatar;
      const data = await request("profile", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: tab === "Profile" ? fields.name : user.name, preferences }) });
      onUser(data.user); setNotice("Changes saved.");
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function signOut(all = false) {
    setBusy(true); setError("");
    try { await onLogout(all); } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  return <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/30 p-4 backdrop-blur-sm" onMouseDown={event => { if (event.target === event.currentTarget && !busy) onClose(); }}>
    <section ref={dialog} role="dialog" aria-modal="true" aria-labelledby="profile-heading" className="flex max-h-[90vh] w-full max-w-xl flex-col rounded-3xl bg-[#fbfaff] shadow-2xl">
      <header className="flex items-center justify-between border-b border-purple-100 p-5"><div className="flex items-center gap-3"><Avatar id={chosenAvatar} size={44}/><div><h2 id="profile-heading" className="text-lg font-bold">Profile & settings</h2><p className="text-xs text-slate-500">@{user.username}</p></div></div><button type="button" disabled={busy} onClick={onClose} aria-label="Close profile settings" className="icon-button"><X size={18}/></button></header>
      <nav aria-label="Profile sections" className="flex flex-wrap gap-2 px-5 pt-4">{[["Profile", UserRound], ["Settings", Settings], ["Appearance", Palette], ["Security", ShieldCheck]].map(([name, Icon]) => <button disabled={busy} key={name} type="button" aria-pressed={tab === name} onClick={() => { setTab(name); setError(""); setNotice(""); }} className={`flex items-center gap-2 rounded-xl px-3 py-2 text-sm ${tab === name ? "bg-lilac font-semibold text-plum" : "text-slate-500 hover:bg-white"}`}><Icon size={15}/>{name}</button>)}</nav>
      <div className="overflow-y-auto p-5">
        {tab === "Appearance" && <form onSubmit={save} className="space-y-5">
          <div><h3 className="text-base font-bold">Make this space yours</h3><p className="mt-1 text-sm text-slate-500">Preview a palette, then save it to your account. Closing without saving restores your theme.</p></div>
          <input type="hidden" name="theme" value={chosenTheme}/>
          <ThemeChoices chosenTheme={chosenTheme} onChange={setChosenTheme}/>
          <button disabled={busy} className="primary-button">{busy ? "Saving…" : "Save appearance"}</button>
        </form>}
        {tab === "Profile" && <form onSubmit={save} className="space-y-4"><fieldset className="space-y-3"><legend className="text-sm font-semibold">Choose your avatar</legend><p className="text-xs leading-5 text-slate-500">Five illustrated companions. Choose the one that feels like you.</p><div className="grid grid-cols-3 gap-2 sm:grid-cols-5">{AVATARS.map(avatar => <button key={avatar.id} type="button" aria-label={`Choose ${avatar.name} avatar`} aria-pressed={chosenAvatar === avatar.id} onClick={() => setChosenAvatar(avatar.id)} className={`flex flex-col items-center gap-2 rounded-xl border p-2 transition ${chosenAvatar === avatar.id ? "border-plum bg-lilac" : "border-transparent hover:bg-lilac/40"}`}><Avatar id={avatar.id} size={40}/><span className="text-[10px] text-slate-600">{avatar.name}</span></button>)}</div></fieldset><TextField label="Display name" name="name" defaultValue={user.name} required maxLength={80}/><TextField label="Username" value={user.username} readOnly/><TextField label="Email" value={user.email} readOnly/><p className="text-xs leading-5 text-slate-500">Username and email cannot be changed yet. Email ownership is not verified. Your chosen avatar appears in the top-right profile button.</p><button disabled={busy} className="primary-button">{busy ? "Saving…" : "Save profile"}</button></form>}
        {tab === "Settings" && <form onSubmit={save} className="space-y-4"><Select label="Default study language" name="language" value={user.preferences?.language || "english"} options={[["english", "English"], ["hindi", "Hindi"], ["hinglish", "Hinglish (Romanised Hindi)"]]}/><Select label="Default quiz difficulty" name="quiz_difficulty" value={user.preferences?.quiz_difficulty || "medium"} options={[["easy", "Easy"], ["medium", "Medium"], ["hard", "Hard"]]}/><Select label="Interface text size" name="font_size" value={user.preferences?.font_size || "normal"} options={[["small", "Compact"], ["normal", "Normal"], ["large", "Larger"]]}/><p className="text-xs leading-5 text-slate-500">Language and difficulty set the initial choices in Learn and Practise; you can still change them for each task. Language quality depends on the configured model.</p><button disabled={busy} className="primary-button">{busy ? "Saving…" : "Save settings"}</button></form>}
        {tab === "Security" && <div className="space-y-6"><form className="space-y-4" onSubmit={async event => { event.preventDefault(); const fields = Object.fromEntries(new FormData(event.currentTarget)); setError(""); if (fields.new_password !== fields.confirm_password) { setError("New passwords do not match."); return; } setBusy(true); try { await request("password", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ current_password: fields.current_password, new_password: fields.new_password }) }); onPasswordChanged(); } catch (e) { setError(e.message); } finally { setBusy(false); } }}><Password label="Current password" name="current_password"/><Password label="New password (10–128 characters)" name="new_password" newPassword/><Password label="Confirm new password" name="confirm_password" newPassword/><p className="text-xs text-slate-500">Changing your password signs out all sessions.</p><button disabled={busy} className="primary-button">{busy ? "Updating…" : "Change password"}</button></form><section className="border-t pt-4"><h3 className="text-sm font-bold">Active sessions</h3>{sessionError && <p role="alert" className="mt-2 text-xs text-rose-600">{sessionError}</p>}{sessions.map(session => <div key={session.id} className="mt-3 rounded-xl bg-white p-3 text-xs text-slate-600"><p className="font-semibold">{session.current ? "This session" : "Other session"}</p><p className="mt-1 break-words">{session.user_agent || "Browser"}</p><p className="mt-1">Last active: {new Date(session.last_seen * 1000).toLocaleString()}</p>{!session.current && <button disabled={busy} type="button" className="mt-2 text-plum underline" onClick={async () => { setBusy(true); try { await request(`sessions/${session.id}`, { method: "DELETE" }); setSessions(items => items.filter(item => item.id !== session.id)); } catch (e) { setError(e.message); } finally { setBusy(false); } }}>Sign out this session</button>}</div>)}</section></div>}
        {error && <p role="alert" className="mt-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}{notice && <p role="status" className="mt-4 text-sm text-emerald-700">{notice}</p>}
      </div>
      <footer className="flex flex-wrap gap-3 border-t border-purple-100 p-5"><button disabled={busy} onClick={() => signOut()} className="secondary-button"><LogOut size={15}/>Sign out</button><button disabled={busy} onClick={() => signOut(true)} className="secondary-button">Sign out all sessions</button></footer>
    </section>
  </div>;
}
function ThemeChoices({ chosenTheme, onChange }) {
  return <div className="space-y-5">{[false, true].map(dark => <fieldset key={String(dark)}>
    <legend className="mb-3 text-sm font-semibold">{dark ? "Dark themes" : "Light themes"}</legend>
    <div className="grid gap-3 sm:grid-cols-2">{THEMES.filter(theme => isDarkTheme(theme.id) === dark).map(theme => <button type="button" key={theme.id} aria-pressed={chosenTheme === theme.id} onClick={() => onChange(theme.id)} className={`overflow-hidden rounded-2xl border text-left transition ${chosenTheme === theme.id ? "border-plum ring-1 ring-plum" : "border-slate-200"}`}>
      <div className="flex h-14 items-center gap-2 p-3" style={{ backgroundColor: theme.colors[0] }}><div className="h-9 w-6 rounded-lg" style={{ backgroundColor: theme.colors[1] }}/><div className="flex-1 space-y-2"><div className="h-2 w-3/4 rounded-full" style={{ backgroundColor: theme.colors[2], opacity: .7 }}/><div className="h-2 w-1/2 rounded-full" style={{ backgroundColor: theme.colors[2], opacity: .25 }}/></div><div className="h-6 w-6 rounded-full" style={{ backgroundColor: theme.colors[2] }}/></div>
      <div className="flex items-center justify-between p-3"><div><p className="font-heading text-sm font-semibold">{theme.name}</p><p className="mt-0.5 text-xs text-slate-500">{theme.detail}</p></div>{chosenTheme === theme.id && <Check size={17} className="text-plum"/>}</div>
    </button>)}</div>
  </fieldset>)}</div>;
}
function TextField({ label, ...props }) { return <label className="block text-sm font-medium">{label}<input {...props} className="mt-2 w-full rounded-xl border border-slate-200 bg-white p-2.5 read-only:bg-slate-50 read-only:text-slate-500"/></label>; }
function Select({ label, name, value, options }) { return <label className="block text-sm font-medium">{label}<select key={value} name={name} defaultValue={value} className="mt-2 w-full rounded-xl border border-slate-200 bg-white p-2.5">{options.map(([id, text]) => <option key={id} value={id}>{text}</option>)}</select></label>; }
function Password({ label, name, newPassword = false }) { const [show, setShow] = useState(false); return <div><label htmlFor={name} className="text-sm font-medium">{label}</label><div className="mt-2 flex gap-2"><input id={name} name={name} type={show ? "text" : "password"} autoComplete={newPassword ? "new-password" : "current-password"} required minLength={newPassword ? 10 : 1} maxLength={128} className="min-w-0 flex-1 rounded-xl border p-2.5"/><button type="button" aria-label={`${show ? "Hide" : "Show"} ${label}`} aria-pressed={show} onClick={() => setShow(!show)} className="secondary-button px-3">{show ? <EyeOff size={18}/> : <Eye size={18}/>}</button></div></div>; }
