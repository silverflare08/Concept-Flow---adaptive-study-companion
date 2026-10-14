import React from "react";

export const AVATARS = [
  { id: "scholar", name: "Iris", background: "#e9e1f8", skin: "#dba783", hair: "#393345", shirt: "#8270ac" },
  { id: "explorer", name: "Hazel", background: "#dceee5", skin: "#a76b48", hair: "#30292a", shirt: "#568873" },
  { id: "scholar-male", name: "Theo", background: "#e0ecfa", skin: "#b77853", hair: "#302b32", shirt: "#567aa0" },
  { id: "explorer-male", name: "Arlo", background: "#fae9d9", skin: "#e2b08e", hair: "#5b4032", shirt: "#b27a57" },
  { id: "owl", name: "Pip", background: "#e8eedc" },
];
export function canonicalAvatarId(id) {
  const legacy = { thinker: "scholar", creator: "explorer", dreamer: "explorer", "thinker-male": "scholar-male" };
  const mapped = legacy[id] || id;
  return AVATARS.some(item => item.id === mapped) ? mapped : "scholar";
}
export default function Avatar({ id = "scholar", size = 40, className = "" }) {
  const person = AVATARS.find(item => item.id === canonicalAvatarId(id));
  id = person.id;
  if (id === "owl") return <svg viewBox="0 0 80 80" width={size} height={size} aria-hidden="true" className={`shrink-0 rounded-full ${className}`}><circle cx="40" cy="40" r="40" fill="#e8eedc"/><path d="M18 20l11 7q11-7 22 0l11-7-3 23c5 20-7 29-19 29S17 60 21 43z" fill="#947654"/><ellipse cx="40" cy="51" rx="17" ry="19" fill="#c5a982"/><circle cx="29" cy="38" r="12" fill="#fff2d7"/><circle cx="51" cy="38" r="12" fill="#fff2d7"/><circle cx="29" cy="38" r="5" fill="#38332e"/><circle cx="51" cy="38" r="5" fill="#38332e"/><circle cx="30" cy="36" r="1.5" fill="white"/><circle cx="52" cy="36" r="1.5" fill="white"/><path d="M35 45h10l-5 7z" fill="#dcaa49"/><path d="M22 48q-6 8 0 15M58 48q6 8 0 15" fill="none" stroke="#765b41" strokeWidth="4" strokeLinecap="round"/></svg>;
  const male = person.id.endsWith("-male");
  return <svg viewBox="0 0 80 80" width={size} height={size} aria-hidden="true" className={`shrink-0 rounded-full ${className}`}>
    <circle cx="40" cy="40" r="40" fill={person.background}/>
    <path d="M10 80c2-19 13-29 30-29s28 10 30 29" fill={person.shirt}/>
    <path d="M31 49h18v11c-5 6-13 6-18 0z" fill={person.skin}/>
    <path d={male ? "M21 35c-3-15 6-25 20-25 15 0 22 12 18 28l-5-10-27-3z" : "M20 36c0-18 8-26 21-26 15 0 22 12 20 29l-2 17H21z"} fill={person.hair}/>
    <ellipse cx="40" cy="35" rx="17" ry="22" fill={person.skin}/>
    <path d={id === "explorer" ? "M22 31c-5-21 15-29 29-18 8 3 10 12 7 20l-8-15c-7 9-14 10-28 13" : id === "creator" ? "M22 30c-6-13 5-23 18-23 16 0 24 13 18 27l-7-15c-6 2-12 11-29 11" : "M22 30c-4-17 12-25 23-20 13 1 20 16 13 25l-5-14c-10 1-18 10-31 9"} fill={person.hair}/>
    <circle cx="33" cy="36" r="1.6" fill="#332b30"/><circle cx="47" cy="36" r="1.6" fill="#332b30"/>
    <path d="M35 45q5 4 10 0" fill="none" stroke="#835648" strokeWidth="1.8" strokeLinecap="round"/>
    {id === "thinker-male" && <path d="M25 43q2 15 15 15t15-15l-6 5q-9 7-18 0z" fill={person.hair} opacity=".8"/>}
    {(id === "scholar" || id === "thinker" || id === "scholar-male") && <g fill="none" stroke={person.hair} strokeWidth="1.5"><rect x="26" y="31" width="12" height="10" rx="4"/><rect x="42" y="31" width="12" height="10" rx="4"/><path d="M38 35h4"/></g>}
    {id === "dreamer" && <path d="M54 16l2-4 2 4 4 2-4 2-2 4-2-4-4-2z" fill="#f9d793"/>}
  </svg>;
}
