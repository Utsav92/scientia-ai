import { useEffect, useState } from "react";
import { api, pollJob, fetchBlobUrl, Answer, Citation, Evidence, StudioResult, GNode } from "../api";
import { CitationCard } from "../components/Evidence";
import MindMap from "../graph/MindMap";
import type { CmpPaper } from "./Compare";

const KINDS = [["overview", "Overview", "Summary of each paper with quotes"], ["mindmap", "Mind map", "Interactive concept map"], ["slides", "Slides", "Slide deck + PDF"],
  ["audio", "Audio overview", "Two-host spoken briefing"], ["video", "Video overview", "Narrated slides (MP4)"]] as const;
type Kind = typeof KINDS[number][0];
type St = { busy: boolean; progress: number; message: string; err: string; res?: StudioResult; urls: Record<string, string> };

function Quote({ q }: { q?: string | null }) { return q ? <p className="border-l-2 border-sky-700 pl-2 mt-1 text-slate-400 text-xs">“{q}”</p> : null; }
function Sect({ title, items }: { title: string; items: { text: string; quote: string | null }[] }) {
  return (<div className="mb-3"><h4 className="text-xs uppercase tracking-wide text-slate-400">{title}</h4>
    {items.length === 0 ? <p className="text-slate-400 text-sm">Not stated in the source.</p> : items.map((e, i) => <details key={i} className="text-sm mb-1"><summary className="cursor-pointer text-slate-200">{e.text}</summary><Quote q={e.quote} /></details>)}</div>);
}

function SlideViewer({ r, pdf, pptx, imgs }: { r: StudioResult; pdf?: string; pptx?: string; imgs: string[] }) {
  const [i, setI] = useState(0); const s = r.slides!; const sl = s[i];
  useEffect(() => { const f = (e: KeyboardEvent) => { if (e.key === "ArrowRight") setI(x => Math.min(x + 1, s.length - 1)); if (e.key === "ArrowLeft") setI(x => Math.max(x - 1, 0)); }; window.addEventListener("keydown", f); return () => window.removeEventListener("keydown", f); }, [s.length]);
  const quotes = sl.bullets.filter(b => b.quote);
  return (<div>{imgs[i] ? <img src={imgs[i]} alt={`Slide ${i + 1}: ${sl.title}`} className="w-full rounded-xl border border-slate-700" /> :
      <div className="aspect-video rounded-xl border border-slate-700 bg-[#0b0e14] p-8 overflow-auto border-l-8 border-l-sky-500"><h3 className="text-2xl font-bold mb-4">{sl.title}</h3>
      <ul className="space-y-3 text-lg">{sl.bullets.map((b, k) => <li key={k} className="list-disc ml-5">{b.text}</li>)}</ul></div>}
    {quotes.length > 0 && <details className="mt-2 text-sm"><summary className="cursor-pointer text-slate-400">Source quotes for this slide</summary>{quotes.map((b, k) => <Quote key={k} q={b.quote} />)}</details>}
    <div className="flex items-center gap-3 mt-2 text-sm"><button className="px-3 py-1 rounded border border-slate-600 disabled:opacity-40" disabled={i === 0} onClick={() => setI(i - 1)}>← Prev</button>
      <span className="text-slate-400">{i + 1} / {s.length}</span><button className="px-3 py-1 rounded border border-slate-600 disabled:opacity-40" disabled={i === s.length - 1} onClick={() => setI(i + 1)}>Next →</button>
      <span className="ml-auto flex gap-2">{pptx && <a href={pptx} download="presentation.pptx" className="px-3 py-1 rounded bg-emerald-600">Download PowerPoint (.pptx)</a>}{pdf && <a href={pdf} download="slides.pdf" className="px-3 py-1 rounded bg-sky-600">Download PDF</a>}</span></div></div>);
}

export default function Studio({ sources, remove, clear, onPaper }: { sources: CmpPaper[]; remove: (id: string) => void; clear: () => void; onPaper: (c: Citation) => void }) {
  const [fluent, setFluent] = useState(true); const [aiDesign, setAiDesign] = useState(false); const [st, setSt] = useState<Partial<Record<Kind, St>>>({}); const [tab, setTab] = useState<Kind | null>(null);
  const [q, setQ] = useState(""); const [ans, setAns] = useState<Answer | null>(null); const [asking, setAsking] = useState(false); const [aerr, setAerr] = useState(""); const [active, setActive] = useState<number | null>(null);
  const [sel, setSel] = useState<GNode | null>(null);
  const ids = sources.map(s => s.id).join(",");
  useEffect(() => { setSt({}); setTab(null); setAns(null); }, [ids]);   // outputs belong to a specific source set

  async function ask() {
    setAsking(true); setAerr(""); setAns(null);
    try { setAns(await api<Answer>("/api/research/ask", { question: q, scope: "both", paper_ids: sources.map(s => s.id), filters: {}, llm_provider: "openai_compatible" })); } catch (e: any) { setAerr(e.message); } finally { setAsking(false); }
  }
  async function gen(kind: Kind) {
    const upd = (p: Partial<St>) => setSt(s => ({ ...s, [kind]: { busy: false, progress: 0, message: "", err: "", urls: {}, ...s[kind], ...p } }));
    upd({ busy: true, progress: 0, message: "starting", err: "", res: undefined, urls: {} }); setTab(kind);
    try {
      const { job_id } = await api<{ job_id: string }>("/api/studio/generate", { paper_ids: sources.map(s => s.id), kind, fluent, ai_design: aiDesign });
      const j = await pollJob(job_id, x => upd({ progress: x.progress, message: x.message }));
      if (j.status === "failed") throw new Error(j.message || "generation failed");
      const res: StudioResult = j.result; const urls: Record<string, string> = {};
      for (const [k, name] of Object.entries(res.files)) urls[k] = await fetchBlobUrl(`/api/studio/file/${res.key}/${name}`);
      for (const [n, name] of (res.images ?? []).entries()) urls[`img${n}`] = await fetchBlobUrl(`/api/studio/file/${res.key}/${name}`);
      upd({ busy: false, res, urls, progress: 1, message: "" });
    } catch (e: any) { upd({ busy: false, err: e.message }); }
  }
  const cur = tab ? st[tab] : undefined; const res = cur?.res;
  const noSrc = sources.length === 0;

  return (<div className="max-w-5xl mx-auto p-6">
    <h2 className="text-xl font-semibold mb-1">Studio</h2>
    <p className="text-sm text-slate-400 mb-4">Pick up to 6 papers as sources, ask them questions, and turn them into an overview, mind map, slides, audio or video. Everything is built from the papers’ own sentences — expand any item to see its source quote.</p>
    <div className="mb-4">
      <h3 className="text-xs uppercase tracking-wide text-slate-400 mb-2">Sources ({sources.length}/6)</h3>
      {noSrc ? <p className="text-slate-300 text-sm">No sources yet. <b>Upload a paper</b> (it’s added automatically) or select a search result and click “Add to sources”.</p> :
        <div className="flex flex-wrap gap-2">{sources.map(p => <span key={p.id} className="px-3 py-1 rounded-full border border-slate-600 text-sm">{p.title ?? p.id}
          <button aria-label={`Remove ${p.title ?? p.id}`} className="ml-2 text-slate-400 hover:text-white" onClick={() => remove(p.id)}>×</button></span>)}
          <button className="text-xs text-slate-400 underline" onClick={clear}>clear all</button></div>}</div>

    <form className="mb-6" onSubmit={e => { e.preventDefault(); ask(); }}>
      <textarea value={q} onChange={e => setQ(e.target.value)} rows={2} aria-label="Question about your sources" placeholder="Ask a question about these papers…" disabled={noSrc}
        className="w-full rounded-xl bg-slate-900 border border-slate-700 focus:border-sky-500 outline-none p-3 disabled:opacity-50" />
      <button disabled={noSrc || asking || q.trim().length < 3} className="mt-2 px-4 py-2 rounded-lg bg-sky-600 disabled:opacity-40">{asking ? "Working…" : "Ask sources"}</button></form>
    {aerr && <p role="alert" className="text-rose-400 mb-3">{aerr}</p>}
    {ans && <div className="mb-8"><div className={`rounded-xl border p-4 ${ans.abstained ? "border-amber-700 bg-amber-950/20" : "border-slate-700 bg-slate-900/60"}`}>
      {ans.abstained && <p className="text-amber-400 text-sm mb-1 font-medium">Not enough evidence in these papers to answer.</p>}<p className="leading-relaxed">{ans.answer}</p></div>
      {Object.values(ans.citations).map(c => <CitationCard key={c.n} c={c} active={active === c.n} onSelect={() => { setActive(c.n); onPaper(c); }} />)}</div>}

    <h3 className="text-xs uppercase tracking-wide text-slate-400 mb-2">Generate</h3>
    <div className="flex flex-wrap gap-x-6 gap-y-1 mb-3 text-sm text-slate-300">
      <label className="flex items-center gap-2"><input type="checkbox" checked={aiDesign} onChange={e => setAiDesign(e.target.checked)} />Slides: let Claude/OpenAI design the deck <span className="text-xs text-slate-400">(sends the extracted sentences to that provider; needs an API key on the server)</span></label>
      <label className="flex items-center gap-2"><input type="checkbox" checked={fluent} onChange={e => setFluent(e.target.checked)} />Audio/video: explain in natural language <span className="text-xs text-slate-400">(local model; numbers and vocabulary are checked against the paper, but subtle wording shifts can slip through — on-screen text stays verbatim. Falls back to the paper’s own sentences if the model isn’t running.)</span></label></div>
    <div className="grid sm:grid-cols-3 lg:grid-cols-5 gap-2 mb-4">{KINDS.map(([k, label, desc]) => { const s = st[k]; return (
      <button key={k} disabled={noSrc || s?.busy} onClick={() => (s?.res ? setTab(k) : gen(k))} className={`text-left rounded-xl border p-3 disabled:opacity-50 ${tab === k ? "border-sky-500 bg-sky-950/30" : "border-slate-700 bg-slate-900/50 hover:border-slate-500"}`}>
        <span className="font-medium block">{label}</span><span className="text-xs text-slate-400">{s?.busy ? `${Math.round(s.progress * 100)}% ${s.message}` : s?.res ? "Ready — view" : desc}</span></button>); })}</div>

    {cur?.err && <p role="alert" className="text-rose-400">{cur.err}</p>}
    {cur?.busy && <p className="text-slate-300 text-sm">Generating… audio and video take a minute or two (offline text-to-speech).</p>}
    {res && tab && (<section className="rounded-xl border border-slate-800 p-4">
      <div className="flex items-center mb-3"><h3 className="font-medium">{KINDS.find(k => k[0] === tab)![1]}</h3>
        <button className="ml-auto text-xs text-slate-400 underline" onClick={() => gen(tab)}>regenerate</button></div>
      <p className="text-xs text-amber-500 mb-3">{res.note}</p>
      {res.fluent_note && <p className="text-xs text-rose-300 mb-3">{res.fluent_note}</p>}
      {res.fluent_stats && <p className="text-xs text-slate-400 mb-3">Natural-language narration passed the source check for {res.fluent_stats.accepted} of {res.fluent_stats.total} segments; the rest use the paper’s own sentences.</p>}
      {tab === "overview" && res.brief && (<>{res.brief.shared_concepts.length > 0 && <p className="text-sm mb-3">Shared concepts: {res.brief.shared_concepts.join(" · ")}</p>}
        {res.brief.papers.map(p => (<div key={p.id} className="mb-6"><h4 className="font-semibold mb-2">{p.title}{p.year ? ` (${p.year})` : ""}</h4>
          {p.sections && p.sections.length > 0 ? p.sections.map(sec => <Sect key={sec.heading} title={sec.heading} items={sec.sentences} />) : <>
          <Sect title="Abstract / opening" items={p.abstract} /><Sect title="Research question" items={p.research_question} /><Sect title="Methodology" items={p.methodology} /><Sect title="Findings" items={p.findings} />
          <Sect title="Quantitative results" items={p.quantitative_results} /><Sect title="Conclusions" items={p.conclusions} /><Sect title="Limitations" items={p.limitations} /><Sect title="Future work" items={p.future_work} /></>}
          {p.entities.length > 0 && <p className="text-xs text-slate-400">Concepts: {p.entities.join(" · ")}</p>}</div>))}</>)}
      {tab === "mindmap" && res.mindmap && (<div><MindMap data={res.mindmap} onSelect={setSel} />
        <div className="mt-3 text-sm rounded-xl border border-slate-800 p-4 min-h-[72px]"><h4 className="text-xs uppercase tracking-wide text-slate-400 mb-1">Selected</h4>{!sel ? <p className="text-slate-400">Click a node to read it in full with its source quote. Use the ‹ / number buttons to collapse or expand a branch; drag to pan, scroll to zoom.</p> : <><p className="font-medium">{sel.label}</p><Quote q={sel.quote} /></>}</div></div>)}
      {tab === "slides" && res.design && <p className="text-xs text-slate-400 mb-2">Theme: <b>{res.design.theme.name}</b>{res.design.report.ai ? ` · designed by ${res.design.report.provider === "anthropic" ? "Claude" : "OpenAI"}: ${res.design.report.headlines[0]}/${res.design.report.headlines[1]} headlines and ${res.design.report.notes[0]}/${res.design.report.notes[1]} speaker notes passed the source check${res.design.report.error ? ` (AI call failed: ${res.design.report.error})` : ""}` : " · built-in designer"}</p>}
      {tab === "slides" && res.slides && <SlideViewer r={res} pdf={cur?.urls.pdf} pptx={cur?.urls.pptx} imgs={(res.images ?? []).map((_, n) => cur?.urls[`img${n}`] ?? "")} />}
      {tab === "audio" && (<>{cur?.urls.audio && <audio controls src={cur.urls.audio} className="w-full mb-4" />}
        <div className="space-y-2 text-sm">{res.transcript?.map((t, i) => <div key={i} className="flex gap-3"><span className={`shrink-0 w-14 font-mono text-xs pt-0.5 ${t.speaker === "A" ? "text-sky-400" : "text-emerald-400"}`}>Host {t.speaker}</span>
          <div><p>{t.text}</p><Quote q={t.quote} /></div></div>)}</div></>)}
      {tab === "video" && cur?.urls.video && <><video controls src={cur.urls.video} className="w-full rounded-lg bg-black" /><p className="text-xs text-slate-400 mt-2">Rendered with {res.renderer === "remotion" ? "Remotion (animated graphics, captions)" : "the basic renderer — install the video/ dependencies for animated graphics"} · {res.duration_s}s</p></>}
    </section>)}
  </div>);
}
