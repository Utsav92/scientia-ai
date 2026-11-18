import { useState } from "react";
import { api, CompareResult, Evidenced } from "../api";

export type CmpPaper = { id: string; title: string | null };
const ROWS: [string, string][] = [["research_question", "Research question"], ["methodology", "Methodology"], ["datasets", "Datasets"], ["findings", "Findings"],
  ["quantitative_results", "Quantitative results"], ["limitations", "Limitations"], ["future_work", "Future work"]];

function Cell({ items }: { items: Evidenced[] }) {
  if (!items.length) return <span className="text-slate-400">Not stated in the source.</span>;
  return <>{items.slice(0, 3).map((e, i) => <details key={i} className="mb-1"><summary className="cursor-pointer text-slate-200">{e.text}</summary>
    <p className="border-l-2 border-sky-700 pl-2 mt-1 text-slate-400">“{e.quote}”</p></details>)}
    {items.length > 3 && <span className="text-xs text-slate-400">+{items.length - 3} more</span>}</>;
}

export default function Compare({ papers, remove, clear }: { papers: CmpPaper[]; remove: (id: string) => void; clear: () => void }) {
  const [res, setRes] = useState<CompareResult | null>(null); const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  const [method, setMethod] = useState<"rules" | "llm">("rules"); const [tensions, setTensions] = useState(false);
  const title = (id: string) => papers.find(p => p.id === id)?.title ?? res?.papers.find(p => p.paper_id === id)?.title ?? id;
  async function run() {
    setBusy(true); setErr(""); setRes(null);
    try { setRes(await api<CompareResult>("/api/research/compare", { paper_ids: papers.map(p => p.id), method, detect_tensions: tensions })); }
    catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }
  return (<div className="max-w-6xl mx-auto p-6">
    <h2 className="text-xl font-semibold mb-1">Compare studies</h2>
    <p className="text-sm text-slate-400 mb-4">Side-by-side view built only from quotes extracted from each paper. Empty cells mean the source did not state it. Uses the same sources as Studio (2–6): uploaded papers are added automatically, or use “Add to sources” in the Selected passage panel.</p>
    {papers.length === 0 ? <p className="text-slate-400">No papers selected yet. Upload a paper, or run a search, select a result, then choose “Add to sources”.</p> :
      <div className="flex flex-wrap gap-2 mb-3">{papers.map(p => <span key={p.id} className="px-3 py-1 rounded-full border border-slate-700 text-sm">{p.title ?? p.id}
        <button aria-label={`Remove ${p.title ?? p.id}`} className="ml-2 text-slate-400 hover:text-white" onClick={() => remove(p.id)}>×</button></span>)}
        <button className="text-xs text-slate-400 underline" onClick={clear}>clear all</button></div>}
    <div className="flex flex-wrap gap-4 items-center mb-4 text-sm">
      <label className="text-slate-400">Extraction <select value={method} onChange={e => setMethod(e.target.value as any)} className="bg-slate-900 border border-slate-700 rounded px-2 py-1 ml-1">
        <option value="rules">Rules (fast)</option><option value="llm">Local LLM</option></select></label>
      <label className="text-slate-400 flex items-center gap-1"><input type="checkbox" checked={tensions} onChange={e => setTensions(e.target.checked)} />Flag candidate contradictions (NLI, slower)</label>
      <button onClick={run} disabled={busy || papers.length < 2 || papers.length > 6} className="ml-auto px-5 py-2 rounded-lg bg-sky-600 disabled:opacity-40">{busy ? "Comparing…" : "Compare"}</button></div>
    {papers.length === 1 && <p className="text-xs text-amber-500 mb-3">Add at least one more paper.</p>}
    {err && <p role="alert" className="text-rose-400 mb-3">{err}</p>}
    {res && (<>
      <div className="overflow-x-auto rounded-xl border border-slate-800"><table className="w-full text-sm align-top"><thead><tr className="bg-slate-900/60 text-left">
        <th className="p-3 w-36 text-slate-400 font-normal">&nbsp;</th>{res.papers.map(p => <th key={p.paper_id} className="p-3 font-medium">{p.title ?? p.paper_id}<span className="block text-xs text-slate-400 font-normal">{p.method} · {p.n_entities} entities</span></th>)}</tr></thead>
        <tbody>{ROWS.map(([k, l]) => <tr key={k} className="border-t border-slate-800">
          <th scope="row" className="p-3 text-left text-xs uppercase tracking-wide text-slate-400 font-normal">{l}</th>
          {res.papers.map(p => <td key={p.paper_id} className="p-3 align-top"><Cell items={res.dimensions[k]?.[p.paper_id] ?? []} /></td>)}</tr>)}</tbody></table></div>
      <h3 className="mt-6 mb-2 text-sm uppercase tracking-wide text-slate-400">Shared concepts</h3>
      <p className="text-sm text-slate-300 mb-2">{res.entities.shared_by_all.length ? res.entities.shared_by_all.join(" · ") : <span className="text-slate-400">No entity appears in every paper.</span>}</p>
      <ul className="text-xs text-slate-400 space-y-1 mb-2">{res.entities.pairs.map((p, i) => <li key={i}>{title(p.a)} ↔ {title(p.b)}: {p.n_shared} shared (Jaccard {p.jaccard}){p.shared.length ? ` — ${p.shared.slice(0, 6).join(", ")}` : ""}</li>)}</ul>
      {res.tensions && (<><h3 className="mt-6 mb-1 text-sm uppercase tracking-wide text-slate-400">Candidate tensions</h3>
        <p className="text-xs text-amber-500 mb-2">{res.tensions.caveat} Checked {res.tensions.pairs_checked} finding pairs{res.tensions.truncated ? " (truncated)" : ""}; threshold {res.tensions.min_prob}.</p>
        {res.tensions.candidates.length === 0 ? <p className="text-slate-400 text-sm">None found above the threshold.</p> :
          res.tensions.candidates.map((t, i) => <div key={i} className="rounded-lg border border-amber-900 bg-amber-950/10 p-3 mb-2 text-sm">
            <p className="text-xs text-slate-400 mb-1">contradiction p={t.contradiction_prob} · shared: {t.shared_entities.join(", ")}</p>
            <p><b>{title(t.paper_a)}:</b> “{t.a.quote}”</p><p><b>{title(t.paper_b)}:</b> “{t.b.quote}”</p></div>)}</>)}
    </>)}
  </div>);
}
