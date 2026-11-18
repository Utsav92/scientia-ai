import { lazy, Suspense, useEffect, useState } from "react";
import { hasToken, login, setToken, Evidence, Citation } from "./api";
import Research from "./pages/Research"; import Library from "./pages/Library"; import Graph from "./pages/Graph"; import ExtractionPanel from "./components/ExtractionPanel"; import Compare, { CmpPaper } from "./pages/Compare"; import Studio from "./pages/Studio";
const Evaluation = lazy(() => import("./pages/Evaluation")); // keeps Plotly out of the main bundle

const NAV = [["ask", "Research Assistant"], ["studio", "Studio"], ["search", "Search Papers"], ["compare", "Compare Studies"], ["graph", "Knowledge Graph"], ["library", "Upload Papers"], ["eval", "Model Evaluation"]] as const;
const NOT_BUILT = new Set<string>();

function Login({ done }: { done: () => void }) {
  const [email, setE] = useState(""); const [pw, setP] = useState(""); const [reg, setReg] = useState(false); const [err, setErr] = useState("");
  return (<form className="max-w-sm mx-auto mt-32 p-6 rounded-xl border border-slate-800 bg-slate-900/60 space-y-3" onSubmit={async e => { e.preventDefault(); try { await login(email, pw, reg); done(); } catch (x: any) { setErr(x.message); } }}>
    <h1 className="text-2xl font-semibold">SCIENTIA AI</h1><p className="text-slate-400 text-sm">Scientific Knowledge Intelligence</p>
    <input className="w-full bg-slate-950 border border-slate-700 rounded p-2" placeholder="Email" value={email} onChange={e => setE(e.target.value)} type="email" />
    <input className="w-full bg-slate-950 border border-slate-700 rounded p-2" placeholder="Password (8+ chars)" value={pw} onChange={e => setP(e.target.value)} type="password" />
    {err && <p role="alert" className="text-rose-400 text-sm">{err}</p>}
    <button className="w-full py-2 rounded bg-sky-600">{reg ? "Create account" : "Sign in"}</button>
    <button type="button" className="text-xs text-slate-400" onClick={() => setReg(!reg)}>{reg ? "Have an account? Sign in" : "New here? Create account"}</button></form>);
}

export default function App() {
  const [authed, setAuthed] = useState(hasToken()); const [page, setPage] = useState<string>("ask"); const [sel, setSel] = useState<Evidence | Citation | null>(null); const [gPaper, setGPaper] = useState(""); const [cmp, setCmp] = useState<CmpPaper[]>([]);
  const addCmp = (p: CmpPaper) => setCmp(c => c.some(x => x.id === p.id) || c.length >= 6 ? c : [...c, p]);
  useEffect(() => { const f = () => setAuthed(false); window.addEventListener("auth-expired", f); return () => window.removeEventListener("auth-expired", f); }, []);
  if (!authed) return <Login done={() => setAuthed(true)} />;
  return (<div className="min-h-screen flex flex-col lg:flex-row">
    <aside className="w-full lg:w-56 border-b lg:border-b-0 lg:border-r border-slate-800 p-4 shrink-0"><h1 className="font-semibold text-lg">SCIENTIA AI</h1><p className="text-xs text-slate-400 mb-6">Scientific Knowledge Intelligence</p>
      <button onClick={() => setPage("library")} className="w-full mb-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-sm font-medium">＋ Upload paper</button>
      <nav className="space-y-1">{NAV.map(([k, l]) => <button key={k} onClick={() => setPage(k)} className={`block w-full text-left px-3 py-2 rounded ${page === k ? "bg-slate-800 text-white" : "text-slate-400 hover:bg-slate-900"}`}>{l}{(k === "compare" || k === "studio") && cmp.length > 0 && <span className="text-[10px] ml-2 text-sky-400">{cmp.length}</span>}{NOT_BUILT.has(k) && <span className="text-[10px] ml-2 text-amber-500">soon</span>}</button>)}</nav>
      <button className="mt-8 text-xs text-slate-400" onClick={() => { setToken(""); setAuthed(false); }}>Sign out</button></aside>
    <main className="flex-1 min-w-0 overflow-auto">
      {(page === "ask" || page === "search") && <Research key={page} mode={page} onPaper={setSel} />}
      {page === "studio" && <Studio sources={cmp} remove={id => setCmp(c => c.filter(x => x.id !== id))} clear={() => setCmp([])} onPaper={setSel} />}{page === "compare" && <Compare papers={cmp} remove={id => setCmp(c => c.filter(x => x.id !== id))} clear={() => setCmp([])} />}{page === "library" && <Library onIndexed={ps => ps.forEach(addCmp)} />}{page === "graph" && <Graph paperId={gPaper} setPaperId={setGPaper} />}{page === "eval" && <Suspense fallback={<p className="p-6 text-slate-400">Loading…</p>}><Evaluation /></Suspense>}
      {NOT_BUILT.has(page) && <div className="max-w-xl mx-auto p-10 text-slate-400"><h2 className="text-lg text-slate-200 mb-2">Not implemented yet</h2><p>This feature is on the roadmap. The API returns 501 for it rather than showing placeholder data.</p></div>}
    </main>
    <aside className="w-full lg:w-80 border-t lg:border-t-0 lg:border-l border-slate-800 p-4 shrink-0 text-sm"><h3 className="uppercase text-xs tracking-wide text-slate-400 mb-2">Selected passage</h3>
      {!sel ? <p className="text-slate-400">Select a result or citation.</p> : <div className="space-y-1"><p className="font-medium">{sel.title ?? "Untitled"}</p>
        <p className="text-slate-400">Section: {sel.section ?? "unlabeled"}</p><p className="text-slate-400 font-mono text-xs break-all">doc {sel.doc_id}</p>
        {"metadata" in sel && Object.entries(sel.metadata).map(([k, v]) => <p key={k} className="text-slate-400">{k}: {String(v)}</p>)}
        {"doi" in sel && sel.doi && <p className="text-slate-400">doi: {sel.doi}</p>}
        <button className="text-sky-400 underline text-xs" onClick={() => { setGPaper(sel.doc_id); setPage("graph"); }}>Open in knowledge graph</button>
        <button className="text-sky-400 underline text-xs ml-3 disabled:text-slate-500 disabled:no-underline" disabled={cmp.some(x => x.id === sel.doc_id) || cmp.length >= 6} onClick={() => addCmp({ id: sel.doc_id, title: sel.title })}>{cmp.some(x => x.id === sel.doc_id) ? "In sources" : "Add to sources"}</button>
        <ExtractionPanel key={sel.doc_id} paperId={sel.doc_id} /></div>}</aside></div>);
}
