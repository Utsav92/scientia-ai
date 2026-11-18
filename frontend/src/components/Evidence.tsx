import { useState } from "react";
import type { Evidence, Citation } from "../api";

export function CitationCard({ c, onSelect, active }: { c: Citation; onSelect?: () => void; active?: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <div id={`cite-${c.n}`} className={`rounded-lg border p-3 mb-2 ${active ? "border-sky-500 bg-sky-950/30" : "border-slate-800 bg-slate-900/50"}`}>
      <button className="text-left w-full" onClick={() => { setOpen(!open); onSelect?.(); }}>
        <span className="text-sky-400 font-mono mr-2">[{c.n}]</span><span className="font-medium">{c.title ?? "Untitled"}</span>
        <span className="text-slate-400 text-xs ml-2">{c.section ?? "unlabeled"}{c.year ? ` · ${c.year}` : ""}</span>
      </button>
      {open && (
        <div className="mt-2 text-sm text-slate-300">
          <p className="whitespace-pre-wrap border-l-2 border-sky-700 pl-3">{c.passage}</p>
          <p className="text-xs text-slate-400 mt-2 font-mono">doc {c.doc_id} · chunk {c.chunk_id} · chars {c.passage.length}</p>
          {c.doi && <a className="text-xs text-sky-400" href={`https://doi.org/${c.doi}`} target="_blank" rel="noreferrer">doi:{c.doi}</a>}
          {c.url && <a className="text-xs text-sky-400 ml-3" href={c.url} target="_blank" rel="noreferrer">source record</a>}
        </div>)}
    </div>);
}

export function ResultRow({ e, i, onSelect }: { e: Evidence; i: number; onSelect: (e: Evidence) => void }) {
  return (
    <button onClick={() => onSelect(e)} className="block text-left w-full rounded-lg border border-slate-800 bg-slate-900/50 hover:border-sky-700 p-3 mb-2">
      <div className="flex justify-between gap-3"><span className="font-medium">{i + 1}. {e.title ?? "Untitled"}</span>
        <span className="text-xs text-slate-400 shrink-0">{e.metadata.domain} · {e.metadata.year ?? "year n/a"}</span></div>
      <p className="text-sm text-slate-400 mt-1 line-clamp-3">{e.passage}</p>
      <p className="text-xs text-slate-400 mt-1 font-mono">score {e.score.toFixed(3)} {Object.entries(e.scores).filter(([, v]) => v != null).map(([k, v]) => `${k}=${(v as number).toFixed(2)}`).join(" ")}</p>
    </button>);
}
