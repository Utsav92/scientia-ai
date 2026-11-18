import { useState } from "react";
import { api, Extraction, Evidenced } from "../api";

function Block({ title, items }: { title: string; items: (Evidenced | null)[] | Evidenced | null }) {
  const arr = (Array.isArray(items) ? items : [items]).filter(Boolean) as Evidenced[];
  return (<div className="mb-3"><h4 className="text-xs uppercase tracking-wide text-slate-400">{title}</h4>
    {arr.length === 0 ? <p className="text-slate-400 text-sm">Not stated in the source.</p> : arr.map((e, i) => (
      <details key={i} className="text-sm mb-1"><summary className="cursor-pointer text-slate-200">{e.text}</summary>
        <p className="border-l-2 border-sky-700 pl-2 mt-1 text-slate-400">“{e.quote}”<span className="block text-xs font-mono text-slate-400">{e.chunk_ids.join(", ")}</span></p></details>))}</div>);
}

export default function ExtractionPanel({ paperId }: { paperId: string }) {
  const [data, setData] = useState<Extraction | null>(null); const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  async function run(method: "rules" | "llm") {
    setBusy(true); setErr("");
    try { setData(await api<Extraction>("/api/research/extract", { paper_id: paperId, method })); } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }
  const x = data?.extraction;
  return (<div className="mt-6"><h3 className="uppercase text-xs tracking-wide text-slate-400 mb-2">Structured extraction</h3>
    <div className="flex gap-2 mb-2"><button disabled={busy} onClick={() => run("rules")} className="px-2 py-1 text-xs rounded border border-slate-700">Rules (fast)</button>
      <button disabled={busy} onClick={() => run("llm")} className="px-2 py-1 text-xs rounded border border-slate-700">Local LLM</button></div>
    {busy && <p className="text-xs text-slate-400">Extracting…</p>}{err && <p role="alert" className="text-xs text-rose-400">{err}</p>}
    {x && (<><p className="text-xs text-slate-400 mb-2">method {x.method}{data!.cached ? " (cached)" : ""} · ungrounded items rejected: {x.dropped_ungrounded}</p>
      <Block title="Research question" items={x.research_question} /><Block title="Methodology" items={x.methodology} /><Block title="Findings" items={x.findings} />
      <Block title="Quantitative results" items={x.quantitative_results} /><Block title="Limitations" items={x.limitations} /><Block title="Future work" items={x.future_work} />
      <h4 className="text-xs uppercase tracking-wide text-slate-400">Entities</h4><p className="text-xs text-slate-400">{x.entities.slice(0, 30).map(e => `${e.canonical} (${e.type.toLowerCase()})`).join(" · ") || "none"}</p></>)}</div>);
}
