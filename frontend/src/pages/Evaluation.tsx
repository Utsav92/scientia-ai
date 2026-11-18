import { useEffect, useState } from "react";
import Plot from "react-plotly.js";
import { api } from "../api";

export default function Evaluation() {
  const [d, setD] = useState<Record<string, any> | null>(null); const [err, setErr] = useState("");
  useEffect(() => { api<Record<string, any>>("/api/evaluation/results").then(setD).catch(e => setErr(e.message)); }, []);
  if (err) return <p className="p-6 text-rose-400">{err}</p>;
  if (!d) return <p className="p-6 text-slate-400">Loading…</p>;
  const ret = Object.entries(d).filter(([, v]) => v.test_results);
  return (<div className="max-w-5xl mx-auto p-6">
    <h2 className="text-xl font-semibold mb-1">Model evaluation</h2>
    <p className="text-sm text-slate-400 mb-4">Every number below is read from files written by actual evaluation runs in <code>outputs/evaluations</code>.</p>
    {ret.length === 0 && <p className="text-slate-400">No retrieval evaluations have been run yet.</p>}
    {ret.map(([name, v]) => { const ms = ["ndcg@10", "recall@10", "mrr@10"]; const sys = Object.keys(v.test_results);
      return (<div key={name} className="mb-8"><h3 className="font-medium">{v.dataset} · {v.embedding} · {v.corpus_size} docs · {v.test_results[sys[0]].n_queries} test queries</h3>
        <Plot data={ms.map(m => ({ type: "bar" as const, name: m, x: sys, y: sys.map(s => v.test_results[s][m]) }))}
          layout={{ barmode: "group", paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", font: { color: "#d6dbe6" }, height: 340, margin: { t: 20 }, yaxis: { range: [0, 1] } }}
          config={{ displayModeBar: false }} style={{ width: "100%" }} />
        <p className="text-xs text-slate-400">{v.fusion_params_tuned_on_dev ? `RRF params tuned on ${v.fusion_params_tuned_on_dev.dev_queries} dev queries (k=${v.fusion_params_tuned_on_dev.rrf_k}, bm25 weight=${v.fusion_params_tuned_on_dev.bm25_weight}).` : "No fusion tuning recorded."}{v.latency?.rerank_ms_per_query != null ? ` Rerank latency ${v.latency.rerank_ms_per_query.toFixed(0)} ms/query.` : ""}</p></div>); })}
  </div>);
}
