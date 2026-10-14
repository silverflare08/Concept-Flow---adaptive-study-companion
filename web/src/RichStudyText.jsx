import React from "react";
import katex from "katex";
import "katex/dist/katex.min.css";

function Equation({ expression, display = false }) {
  try {
    const html = katex.renderToString(expression, { displayMode: display, throwOnError: true,
      trust: false, strict: "warn", output: "htmlAndMathml", maxExpand: 500 });
    return <span className={display ? "block overflow-x-auto py-2" : "inline-block max-w-full align-middle"} dangerouslySetInnerHTML={{ __html: html }}/>;
  } catch {
    return <span className="font-mono text-sm" title="This expression needs checking in the original source">{expression}</span>;
  }
}

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
    .replace(/\\([*_#`\[\]()])/g, "$1")
    .replace(/\\\\\s*/g, "\n")
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
  return text.replace(/\s\*\s/g, " × ").replace(/\\([A-Za-z]+)/g, "$1").replace(/\{([^{}]+)\}/g, "$1");
}

function Inline({ text }) {
  return String(text).split(/(\b[A-Za-z0-9][A-Za-z0-9_.-]*\.(?:pdf|mp4|mp3|wav|m4a|mov|webm|mkv|docx|pptx)\b|\$\$.*?\$\$|\$[^$]+\$|\\\(.*?\\\)|\\\[.*?\\\]|\*\*.*?\*\*|`.*?`|(?<![A-Za-z0-9])[A-Za-z]\^(?:\{[^{}]+\}|[A-Za-z0-9]+)|(?<![A-Za-z0-9])[A-Za-z]_(?:\{[^{}]+\}|[A-Za-z0-9]+))/g).filter(Boolean).map((part, index) => {
    if (/\.(?:pdf|mp4|mp3|wav|m4a|mov|webm|mkv|docx|pptx)$/i.test(part)) return <React.Fragment key={index}>{part}</React.Fragment>;
    if (part.startsWith("$$") && part.endsWith("$$")) return <Equation key={index} expression={part.slice(2, -2)} display/>;
    if (part.startsWith("$") && part.endsWith("$")) return <Equation key={index} expression={part.slice(1, -1)}/>;
    if (/^\\[([]/.test(part)) return <Equation key={index} expression={part.slice(2, -2)} display={part.startsWith("\\[")}/>;
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={index}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`")) return <code key={index} className="rounded bg-slate-100 px-1.5 py-0.5 text-[.92em] text-plum">{part.slice(1, -1)}</code>;
    if (/^[A-Za-z][\^_](?:\{[^{}]+\}|[A-Za-z0-9]+)$/.test(part)) return <Equation key={index} expression={part.replace(/^([A-Za-z])([\^_])([A-Za-z0-9]+)$/, "$1$2{$3}")}/>;
    return <React.Fragment key={index}>{humanizeMath(part).replace(/(^|\s)\*+(?=\s|$)/g, "$1")}</React.Fragment>;
  });
}

export default function RichStudyText({ text, className = "" }) {
  const normalized = String(text || "").replace(/\$\$([\s\S]*?)\$\$/g, (_, equation) => `$$${equation.replace(/\r?\n/g, " ")}$$`)
    .replace(/\\\[([\s\S]*?)\\\]/g, (_, equation) => `\\[${equation.replace(/\r?\n/g, " ")}\\]`);
  const lines = normalized.split(/\r?\n/);
  const consumed = new Set();
  return <article className={`study-rich-text space-y-3 text-[15px] leading-7 text-slate-700 ${className}`}>
    {lines.map((line, index) => {
      if (consumed.has(index)) return null;
      const clean = line.trim();
      if (/^#{1,6}\s+(?:Sources for this section|Source references|Sources|Citations)\s*$/i.test(clean)) {
        const references = [];
        for (let row = index + 1; row < lines.length && !/^\s*(?:#{1,6}\s|---+)/.test(lines[row]); row++) {
          consumed.add(row);
          if (lines[row].trim()) references.push(lines[row].trim().replace(/^[-*•]\s+/, ""));
        }
        return <details key={index} className="text-[11px] leading-4 text-slate-400"><summary className="cursor-pointer hover:text-slate-600">Sources ({references.length})</summary><div className="mt-1 space-y-0.5">{references.map((reference, number) => <p key={number} className="truncate" title={reference}>{reference}</p>)}</div></details>;
      }
      if (clean.startsWith("|") && /^\s*\|?[\s:|-]+\|?\s*$/.test(lines[index + 1] || "")) {
        consumed.add(index + 1);
        const cells = value => value.trim().replace(/^\||\|$/g, "").split("|").map(cell => cell.trim());
        const rows = [];
        for (let row = index + 2; row < lines.length && lines[row].trim().startsWith("|"); row++) { rows.push(cells(lines[row])); consumed.add(row); }
        return <div key={index} className="overflow-x-auto rounded-xl border border-slate-200"><table className="w-full text-left text-sm"><thead className="bg-lilac/50"><tr>{cells(clean).map((cell, column) => <th key={column} className="border-b border-slate-200 px-4 py-2"><Inline text={cell}/></th>)}</tr></thead><tbody>{rows.map((row, number) => <tr key={number}>{row.map((cell, column) => <td key={column} className="border-b border-slate-100 px-4 py-2"><Inline text={cell}/></td>)}</tr>)}</tbody></table></div>;
      }
      if (!clean) return <div key={index} className="h-1"/>;
      if (/^\*\*[^*]+\*\*:?$/.test(clean)) return <h4 key={index} className="mt-5 border-b border-lavender/60 pb-2 text-base font-extrabold text-slate-800"><Inline text={clean.replace(/^\*\*|\*\*:?$/g, "")}/></h4>;
      if (/^###\s/.test(clean)) return <h4 key={index} className="mt-5 border-b border-lavender/60 pb-2 text-base font-extrabold text-slate-800"><Inline text={clean.replace(/^###\s+/, "")}/></h4>;
      if (/^##\s/.test(clean)) return <h3 key={index} className="mt-6 rounded-xl bg-lilac/45 px-4 py-2 text-lg font-extrabold text-slate-800"><Inline text={clean.replace(/^##\s+/, "")}/></h3>;
      if (/^#\s/.test(clean)) return <h2 key={index} className="mt-6 text-xl font-black tracking-tight text-plum"><Inline text={clean.replace(/^#\s+/, "")}/></h2>;
      if (/^[-*•]\s/.test(clean)) return <div key={index} className="flex gap-3 rounded-xl bg-slate-50/80 px-3 py-2"><span className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-plum"/><p><Inline text={clean.replace(/^[-*•]\s+/, "")}/></p></div>;
      if (/^\d+[.)]\s/.test(clean)) return <div key={index} className="flex gap-3 rounded-xl border border-slate-100 bg-white px-3 py-2 shadow-sm"><span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-plum text-xs font-bold text-white">{clean.match(/^\d+/)?.[0]}</span><p><Inline text={clean.replace(/^\d+[.)]\s+/, "")}/></p></div>;
      if (/^>\s?/.test(clean)) return <p key={index} className="rounded-r-xl border-l-4 border-lavender bg-lilac/25 px-4 py-2"><Inline text={clean.replace(/^>\s?/, "")}/></p>;
      if (/^---+$/.test(clean)) return <hr key={index} className="my-4 border-slate-200"/>;
      if (/^[^:]{2,35}:\s+/.test(clean)) { const [label, ...rest] = clean.split(":"); return <p key={index} className="rounded-xl bg-sky/25 px-4 py-3"><strong className="text-slate-800">{label}:</strong> <Inline text={rest.join(":").trim()}/></p>; }
      if (/[=≤≥≈]|√|Σ|∫/.test(clean) && clean.length < 180) return <p key={index} className="overflow-x-auto rounded-xl border border-lavender/60 bg-[#fbfaff] px-4 py-3 text-center font-semibold tracking-wide text-slate-800"><Inline text={clean}/></p>;
      return <p key={index} className="max-w-none"><Inline text={clean}/></p>;
    })}
  </article>;
}
