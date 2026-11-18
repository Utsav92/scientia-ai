import { useEffect, useMemo, useRef, useState } from "react";
import type cytoscape from "cytoscape";
import { api, GraphData, GNode } from "../api";
import GraphView, { DOMAIN_COLOR } from "../graph/GraphView";

const MODES = [["concept", "Concept graph"], ["paper", "Paper graph"], ["evidence", "Evidence graph"]] as const;
const KINDS = [["extracted", "Extracted from text"], ["semantic", "Semantic similarity (not citations)"], ["citation", "Verified citations"]] as const;

export default function Graph({ paperId, setPaperId }: { paperId: string; setPaperId: (id: string) => void }) {
  const [input, setInput] = useState(paperId); const [mode, setMode] = useState<"concept" | "paper" | "evidence">("concept");
  const [max, setMax] = useState(40); const [data, setData] = useState<GraphData | null>(null); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const [kinds, setKinds] = useState<string[]>(["extracted", "semantic", "citation"]); const [domains, setDomains] = useState<string[]>([]);
  const [sel, setSel] = useState<GNode | null>(null); const [find, setFind] = useState(""); const cy = useRef<cytoscape.Core | null>(null);
  const [overview, setOverview] = useState<any>(null);

  useEffect(() => { api("/api/graph/summary/overview").then(setOverview).catch(() => {}); }, []);
  async function load(id = input) {
    if (!id) return; setBusy(true); setErr(""); setSel(null);
    try { setData(await api<GraphData>(`/api/graph/${encodeURIComponent(id)}?mode=${mode}&max_nodes=${max}${domains.length ? `&domains=${domains.join(",")}` : ""}`)); }
    catch (e: any) { setErr(e.message); setData(null); } finally { setBusy(false); }
  }
  useEffect(() => { if (paperId) { setInput(paperId); load(paperId); } }, [paperId, mode, domains]);
  // memoised: a fresh object every render makes GraphView rebuild (and re-layout) the whole graph on any state change, e.g. selecting a node
  const shown: GraphData | null = useMemo(() => data && { ...data, edges: data.edges.filter(e => kinds.includes(e.kind)) }, [data, kinds]);
  const exportJson = () => { if (!shown) return; const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([JSON.stringify(shown, null, 1)], { type: "application/json" })); a.download = `graph-${input}.json`; a.click(); };
  const exportPng = () => { const u = cy.current?.png({ full: true, bg: "#020617", scale: 2 }); if (u) { const a = document.createElement("a"); a.href = u; a.download = `graph-${input}.png`; a.click(); } };

  return (<div className="max-w-6xl mx-auto p-6">
    <h2 className="text-xl font-semibold mb-1">Knowledge graph</h2>
    <p className="text-sm text-slate-400 mb-4">Edges are labelled by provenance. Dashed lines are embedding similarity, <b>not</b> citations. This corpus carries no bibliographic metadata, so citation edges appear only if verified links were loaded.</p>
    <form className="flex flex-wrap gap-2 mb-3" onSubmit={e => { e.preventDefault(); if (input !== paperId) setPaperId(input); else load(); }}>
      <input value={input} onChange={e => setInput(e.target.value)} placeholder="Paper id (select a result, or paste an id)" aria-label="Paper id" className="flex-1 min-w-[220px] bg-slate-900 border border-slate-700 rounded px-3 py-2" />
      <button className="px-4 py-2 rounded bg-sky-600 disabled:opacity-40" disabled={!input || busy}>{busy ? "Loading…" : "Explore"}</button></form>
    <div className="flex flex-wrap gap-2 items-center mb-3 text-sm">
      {MODES.map(([k, l]) => <button key={k} onClick={() => setMode(k)} className={`px-3 py-1 rounded-full border ${mode === k ? "bg-sky-900 border-sky-500" : "border-slate-700 text-slate-400"}`}>{l}</button>)}
      <label className="ml-2 text-slate-400">Max nodes <input type="range" min={10} max={120} value={max} onChange={e => setMax(+e.target.value)} onPointerUp={() => load()} onKeyUp={() => load()} aria-label="Max nodes" /> {max}</label>
      <input value={find} onChange={e => setFind(e.target.value)} placeholder="Find node…" aria-label="Find node" className="bg-slate-900 border border-slate-700 rounded px-2 py-1 ml-auto" />
      <button onClick={exportJson} className="px-3 py-1 rounded border border-slate-700">Export JSON</button><button onClick={exportPng} className="px-3 py-1 rounded border border-slate-700">Export PNG</button></div>
    <div className="flex flex-wrap gap-3 mb-3 text-xs">
      {KINDS.map(([k, l]) => <label key={k} className="flex items-center gap-1 text-slate-400"><input type="checkbox" checked={kinds.includes(k)} onChange={() => setKinds(kinds.includes(k) ? kinds.filter(x => x !== k) : [...kinds, k])} />{l}</label>)}
      {Object.entries(DOMAIN_COLOR).filter(([d]) => d !== "other").map(([d, c]) => <button key={d} onClick={() => setDomains(domains.includes(d) ? domains.filter(x => x !== d) : [...domains, d])}
        className={`px-2 rounded-full border ${domains.includes(d) ? "border-white" : "border-slate-700"}`} style={{ color: c }}>● {d}</button>)}
      {domains.length > 0 && <button className="text-slate-400 underline" onClick={() => { setDomains([]); }}>clear</button>}
</div>
    {err && <p role="alert" className="text-rose-400 mb-3">{err}</p>}
    {shown ? (<div className="grid lg:grid-cols-[1fr_280px] gap-4">
      <div><GraphView data={shown} onSelect={setSel} cyRef={cy} highlight={find} />
        <p className="text-xs text-slate-400 mt-1">{shown.nodes.length} nodes · {shown.edges.length} edges{shown.truncated ? " · truncated to the node limit" : ""} · scroll to zoom, drag to pan</p></div>
      <aside className="text-sm space-y-3">
        <div className="rounded-lg border border-slate-800 p-3"><h3 className="text-xs uppercase text-slate-400 mb-1">Selected</h3>
          {!sel ? <p className="text-slate-400">Click a node.</p> : <><p className="font-medium">{sel.label}</p><p className="text-slate-400">{sel.kind}{sel.etype ? ` · ${sel.etype}` : ""}{sel.domain ? ` · ${sel.domain}` : ""}{sel.year ? ` · ${sel.year}` : ""}</p>
            {sel.quote && <p className="mt-2 border-l-2 border-sky-700 pl-2 text-slate-300">“{sel.quote}”</p>}
            {sel.kind === "paper" && sel.doc_id && <button className="mt-2 text-sky-400 underline" onClick={() => { setPaperId(sel.doc_id!); }}>Center graph on this paper</button>}</>}</div>
        <div className="rounded-lg border border-slate-800 p-3"><h3 className="text-xs uppercase text-slate-400 mb-1">Related papers</h3>
          {shown.related.shared_entity.slice(0, 5).map(r => <p key={r.paper_id} className="mb-1"><button className="text-left text-sky-300 hover:underline" onClick={() => setPaperId(r.paper_id)}>{r.title}</button><span className="block text-xs text-slate-400">shares: {r.shared_entities.slice(0, 4).join(", ")}</span></p>)}
          {shown.related.shared_entity.length === 0 && <p className="text-slate-400">None found via shared entities.</p>}</div></aside></div>)
      : overview && !busy && (<div className="rounded-lg border border-slate-800 p-4 text-sm"><h3 className="font-medium mb-2">Corpus graph overview</h3>
        <p className="text-slate-400 mb-2">{overview.stats.nodes.toLocaleString()} nodes · {overview.stats.edges.toLocaleString()} edges · citation edges: {overview.stats.citation_edges}</p>
        <p className="text-slate-400 mb-1">Research clusters (entity co-occurrence communities):</p>
        <ul className="space-y-1">{overview.clusters.map((c: any) => <li key={c.cluster} className="text-slate-300">{c.size} entities — {c.top_entities.join(", ")}</li>)}</ul></div>)}
  </div>);
}
