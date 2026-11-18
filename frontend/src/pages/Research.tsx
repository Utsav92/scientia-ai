import { useState } from "react";
import { api, Answer, Citation, Evidence } from "../api";
import { CitationCard, ResultRow } from "../components/Evidence";

const DOMAINS = ["physics", "chemistry", "biology", "ai_cs"] as const;
const STATUS_STYLE: Record<string, string> = { supported: "text-emerald-400", unsupported: "text-rose-400", uncited: "text-amber-400", interpretation: "text-slate-400", invalid_citation: "text-rose-400" };

export default function Research({ onPaper, mode }: { onPaper: (e: Evidence | Citation) => void; mode: "ask" | "search" }) {
  const [q, setQ] = useState(""); const [busy, setBusy] = useState(false); const [err, setErr] = useState("");
  const [ans, setAns] = useState<Answer | null>(null); const [hits, setHits] = useState<Evidence[] | null>(null);
  const [domains, setDomains] = useState<string[]>([]); const [active, setActive] = useState<number | null>(null);
  const [scope, setScope] = useState<"shared" | "private" | "both">("shared");
  const filters = { domains: domains.length ? domains : null };

  async function run() {
    setBusy(true); setErr(""); setAns(null); setHits(null);
    try {
      if (mode === "ask") setAns(await api<Answer>("/api/research/ask", { question: q, scope, filters }));
      else setHits((await api<{ results: Evidence[] }>("/api/search", { query: q, scope, filters })).results);
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }
  const renderAnswer = (t: string) => t.split(/(\[\d+\])/g).map((p, i) => {
    const m = p.match(/^\[(\d+)\]$/);
    return m ? <mark key={i} className="cite" onClick={() => { setActive(+m[1]); document.getElementById(`cite-${m[1]}`)?.scrollIntoView({ behavior: "smooth", block: "center" }); }}>{p}</mark> : <span key={i}>{p}</span>;
  });

  return (
    <div className="max-w-4xl mx-auto p-6">
      <form onSubmit={e => { e.preventDefault(); run(); }}>
        <textarea value={q} onChange={e => setQ(e.target.value)} rows={2} aria-label="Research question"
          placeholder="Ask a question across the indexed scientific papers…"
          className="w-full rounded-xl bg-slate-900 border border-slate-700 focus:border-sky-500 outline-none p-4 text-lg" />
        <div className="flex flex-wrap gap-2 items-center mt-3">
          {DOMAINS.map(d => <button type="button" key={d} onClick={() => setDomains(domains.includes(d) ? domains.filter(x => x !== d) : [...domains, d])}
            className={`px-3 py-1 rounded-full text-sm border ${domains.includes(d) ? "bg-sky-900 border-sky-500" : "border-slate-700 text-slate-400"}`}>{d}</button>)}
          <select value={scope} onChange={e => setScope(e.target.value as any)} className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-sm" aria-label="Scope">
            <option value="shared">Shared corpus</option><option value="private">My uploads</option><option value="both">Both</option></select>
          <button disabled={busy || q.trim().length < 3} className="ml-auto px-5 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 disabled:opacity-40">{busy ? "Working…" : mode === "ask" ? "Research" : "Search"}</button>
        </div>
      </form>
      {err && <p role="alert" className="mt-4 text-rose-400">{err}</p>}
      {ans && (<section className="mt-6">
        <div className={`rounded-xl border p-5 ${ans.abstained ? "border-amber-700 bg-amber-950/20" : "border-slate-700 bg-slate-900/60"}`}>
          {ans.abstained && <p className="text-amber-400 text-sm mb-2 font-medium">Abstained — insufficient evidence in the indexed corpus</p>}
          <p className="leading-relaxed">{renderAnswer(ans.answer)}</p>
          {ans.note && <p className="text-xs text-slate-400 mt-3">{ans.note}</p>}
          <p className="text-xs text-slate-400 mt-3">Generator: {ans.llm ?? "n/a"} · {ans.latency_s}s · evidence passages {ans.coverage.evidence_passages ?? 0}
            {ans.verification?.claim_support_rate != null && ` · draft claims supported ${(ans.verification.claim_support_rate * 100).toFixed(0)}% (unsupported claims were removed)`}</p>
        </div>
        {ans.verification && <details className="mt-3 text-sm"><summary className="cursor-pointer text-slate-400">Citation verification of the draft ({ans.verification.claims.length} statements)</summary>
          <ul className="mt-2 space-y-1">{ans.verification.claims.map((c, i) => <li key={i}><span className={`font-mono text-xs mr-2 ${STATUS_STYLE[c.status]}`}>{c.status}</span>{c.text}</li>)}</ul></details>}
        <h3 className="mt-6 mb-2 text-sm uppercase tracking-wide text-slate-400">Evidence</h3>
        {Object.values(ans.citations).map(c => <CitationCard key={c.n} c={c} active={active === c.n} onSelect={() => { setActive(c.n); onPaper(c); }} />)}
      </section>)}
      {hits && <section className="mt-6">{hits.length === 0 && <p className="text-slate-400">No matching passages.</p>}{hits.map((h, i) => <ResultRow key={h.chunk_id} e={h} i={i} onSelect={onPaper} />)}</section>}
    </div>);
}
