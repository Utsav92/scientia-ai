import { useRef, useState } from "react";
import { api, pollJob } from "../api";

import type { CmpPaper } from "./Compare";

export default function Library({ onIndexed }: { onIndexed?: (p: CmpPaper[]) => void }) {
  const [files, setFiles] = useState<File[]>([]); const [st, setSt] = useState<any>(null); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false); const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const addFiles = (l: FileList | null) => { if (!l) return; const pdfs = Array.from(l).filter(f => f.name.toLowerCase().endsWith(".pdf")); setErr(pdfs.length < l.length ? "Only PDF files are accepted; others were skipped." : ""); setFiles(pdfs); setSt(null); };
  async function up() {
    if (!files.length) return; setErr(""); setBusy(true); const f = new FormData(); files.forEach(x => f.append("files", x));
    try { const { job_id } = await api<{ job_id: string }>("/api/documents/upload", f); const j = await pollJob(job_id, setSt); onIndexed?.((j.result?.files ?? []).filter((x: any) => x.doc_id && !x.error).map((x: any) => ({ id: x.doc_id, title: x.title || x.file.replace(/\.pdf$/i, "") }))); } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }
  return (<div className="max-w-3xl mx-auto p-6"><h2 className="text-xl font-semibold mb-1">Upload papers</h2>
    <p className="text-sm text-slate-400 mb-4">PDFs are parsed, chunked and indexed in a private partition visible only to your account. Uploaded papers are added to your Studio sources automatically.</p>
    <div onDragOver={e => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={e => { e.preventDefault(); setOver(false); addFiles(e.dataTransfer.files); }}
      className={`rounded-2xl border-2 border-dashed p-10 text-center ${over ? "border-sky-400 bg-sky-950/30" : "border-slate-600 bg-slate-900/40"}`}>
      <p className="text-slate-200 mb-1">Drag PDF papers here</p><p className="text-slate-400 text-sm mb-4">or</p>
      <button type="button" onClick={() => input.current?.click()} className="px-5 py-2.5 rounded-lg bg-sky-600 hover:bg-sky-500 font-medium">Choose PDF files</button>
      <input ref={input} type="file" accept="application/pdf,.pdf" multiple className="sr-only" aria-label="PDF files" onChange={e => addFiles(e.target.files)} /></div>
    {files.length > 0 && <div className="mt-4"><ul className="text-sm text-slate-300 mb-3">{files.map((f, i) => <li key={i}>{f.name} <span className="text-slate-400">· {(f.size / 1024 / 1024).toFixed(1)} MB</span></li>)}</ul>
      <button onClick={up} disabled={busy} className="px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40">{busy ? "Uploading…" : `Upload & index ${files.length} file${files.length > 1 ? "s" : ""}`}</button></div>}
    {err && <p role="alert" className="text-rose-400 mt-3">{err}</p>}
    {st && <div className="mt-4 text-sm"><p>Status: <b>{st.status}</b> {Math.round(st.progress * 100)}% {st.message}</p>
      {st.result?.files?.map((f: any, i: number) => <p key={i} className={f.error ? "text-rose-400" : "text-slate-300"}>{f.file}: {f.error ?? `${f.chunks ?? 0} chunks${f.duplicate ? " (already in library)" : ""}${f.doi ? ` · doi ${f.doi}` : ""}`}</p>)}</div>}
  </div>);
}
