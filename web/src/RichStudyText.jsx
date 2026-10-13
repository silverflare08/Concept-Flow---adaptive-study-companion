import React from "react";

const SYMBOLS = {
  "\\times": "×", "\\cdot": "·", "\\div": "÷", "\\pm": "±", "\\mp": "∓",
  "\\leq": "≤", "\\le": "≤", "\\geq": "≥", "\\ge": "≥", "\\neq": "≠",
  "\\approx": "≈", "\\equiv": "≡", "\\infty": "∞", "\\pi": "π", "\\theta": "θ",
  "\\alpha": "α", "\\beta": "β", "\\gamma": "γ", "\\delta": "δ", "\\lambda": "λ",
  "\\mu": "μ", "\\sigma": "σ", "\\sum": "Σ", "\\prod": "Π", "\\int": "∫",
  "\\rightarrow": "→", "\\to": "→", "\\leftarrow": "←", "\\Rightarrow": "⇒",
  "\\in": "∈", "\\notin": "∉", "\\subset": "⊂", "\\cup": "∪", "\\cap": "∩",
};
const SUPER = { 0: "⁰", 1: "¹", 2: "²", 3: "³", 4: "⁴", 5: "⁵", 6: "⁶", 7: "⁷", 8: "⁸", 9: "⁹", "+": "⁺", "-": "⁻" };
const SUB = { 0: "₀", 1: "₁", 2: "₂", 3: "₃", 4: "₄", 5: "₅", 6: "₆", 7: "₇", 8: "₈", 9: "₉", "+": "₊", "-": "₋" };

function digits(value, table) { return [...value].map(char => table[char] || char).join(""); }

export function humanizeMath(value = "") {
  let text = String(value)
    .replace(/\\\[|\\\]|\\\(|\\\)|\$\$/g, "")
    .replace(/\$(.*?)\$/g, "$1")
    .replace(/\\frac\{([^{}]+)\}\{([^{}]+)\}/g, "($1) ÷ ($2)")
    .replace(/\\sqrt\{([^{}]+)\}/g, "√($1)")
    .replace(/\^\{([0-9+\-]+)\}/g, (_, number) => digits(number, SUPER))
    .replace(/_\{([0-9+\-]+)\}/g, (_, number) => digits(number, SUB))
    .replace(/\^([0-9])/g, (_, number) => digits(number, SUPER))
    .replace(/_([0-9])/g, (_, number) => digits(number, SUB))
    .replace(/\\text\{([^{}]+)\}/g, "$1")
    .replace(/\\(?:left|right|mathrm|mathbf|operatorname)\b/g, "");
  Object.entries(SYMBOLS).forEach(([command, symbol]) => { text = text.split(command).join(symbol); });
  return text.replace(/\\([A-Za-z]+)/g, "$1").replace(/\{([^{}]+)\}/g, "$1");
}

function Inline({ text }) {
  return humanizeMath(text).split(/(\*\*.*?\*\*|`.*?`)/g).filter(Boolean).map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={index}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`")) return <code key={index} className="rounded bg-slate-100 px-1.5 py-0.5 text-[.92em] text-plum">{part.slice(1, -1)}</code>;
    return <React.Fragment key={index}>{part}</React.Fragment>;
  });
}

export default function RichStudyText({ text, className = "" }) {
  const lines = String(text || "").split(/\r?\n/);
  return <div className={`study-rich-text space-y-2 text-[15px] leading-7 text-slate-700 ${className}`}>
    {lines.map((line, index) => {
      const clean = line.trim();
      if (!clean) return <div key={index} className="h-1"/>;
      if (/^###\s/.test(clean)) return <h4 key={index} className="pt-2 text-base font-bold text-slate-800"><Inline text={clean.replace(/^###\s+/, "")}/></h4>;
      if (/^##\s/.test(clean)) return <h3 key={index} className="pt-3 text-lg font-extrabold text-slate-800"><Inline text={clean.replace(/^##\s+/, "")}/></h3>;
      if (/^#\s/.test(clean)) return <h2 key={index} className="pt-3 text-xl font-extrabold text-slate-800"><Inline text={clean.replace(/^#\s+/, "")}/></h2>;
      if (/^[-*]\s/.test(clean)) return <div key={index} className="flex gap-2 pl-2"><span className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-plum"/><p><Inline text={clean.replace(/^[-*]\s+/, "")}/></p></div>;
      if (/^\d+[.)]\s/.test(clean)) return <div key={index} className="flex gap-2 pl-2"><span className="font-bold text-plum">{clean.match(/^\d+/)?.[0]}.</span><p><Inline text={clean.replace(/^\d+[.)]\s+/, "")}/></p></div>;
      if (/^>\s?/.test(clean)) return <p key={index} className="rounded-r-xl border-l-4 border-lavender bg-lilac/25 px-4 py-2"><Inline text={clean.replace(/^>\s?/, "")}/></p>;
      if (/^---+$/.test(clean)) return <hr key={index} className="my-4 border-slate-200"/>;
      return <p key={index}><Inline text={clean}/></p>;
    })}
  </div>;
}
