export type Evidence = { doc_id: string; chunk_id: string; title: string | null; section: string | null; score: number; passage: string;
  char_start: number; char_end: number; metadata: Record<string, any>; citation: string; scores: Record<string, number | null> };
export type Citation = { n: number; doc_id: string; chunk_id: string; title: string | null; section: string | null; passage: string; doi: string | null; url: string | null; year: number | null; label: string };
export type Claim = { text: string; status: string; markers: number[]; support: any };
export type Answer = { answer: string; abstained: boolean; citations: Record<string, Citation>; retrieved: Evidence[]; llm: string | null; note?: string;
  coverage: Record<string, any>; verification: { claims: Claim[]; claim_support_rate: number | null; unsupported: string[] } | null; understanding: any; latency_s: number };

let token = localStorage.getItem("token") || "";
export const setToken = (t: string) => { token = t; t ? localStorage.setItem("token", t) : localStorage.removeItem("token"); };
export const hasToken = () => !!token;

export async function api<T>(path: string, body?: unknown, method = body ? "POST" : "GET"): Promise<T> {
  const isForm = body instanceof FormData;
  const r = await fetch(path, { method, headers: { ...(isForm ? {} : { "Content-Type": "application/json" }), Authorization: `Bearer ${token}` },
    body: body === undefined ? undefined : isForm ? body : JSON.stringify(body) });
  if (r.status === 401 && token) { setToken(""); window.dispatchEvent(new Event("auth-expired")); throw new Error("Session expired — please sign in again."); }
  if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(typeof d.detail === "string" ? d.detail : `${r.status} ${r.statusText}`); }
  return r.json();
}
export async function login(email: string, password: string, register = false) {
  if (register) await api("/api/auth/register", { email, password });
  const t = await api<{ access_token: string }>("/api/auth/login", { email, password }); setToken(t.access_token);
}
export async function pollJob(id: string, onUpdate: (j: any) => void) {
  for (;;) { const j = await api<any>(`/api/jobs/${id}`); onUpdate(j); if (j.status === "done" || j.status === "failed") return j; await new Promise(r => setTimeout(r, 1000)); }
}

export type GNode = { id: string; kind: string; label: string; domain?: string; year?: number; etype?: string; doc_id?: string; quote?: string; chunk_ids?: string[] };
export type GEdge = { source: string; target: string; rel: string; kind: "extracted" | "semantic" | "citation"; quote?: string; score?: number };
export type GraphData = { nodes: GNode[]; edges: GEdge[]; truncated?: boolean; mode: string; related: { shared_entity: any[]; semantic_similarity: any[]; citations: any[] } };
export type Evidenced = { text: string; quote: string; chunk_ids: string[] };
export type Extraction = { extraction: { paper_id: string; method: string; research_question: Evidenced | null; methodology: Evidenced | null; hypothesis: Evidenced | null;
  findings: Evidenced[]; quantitative_results: Evidenced[]; limitations: Evidenced[]; future_work: Evidenced[]; datasets: Evidenced[]; entities: { text: string; type: string; canonical: string }[]; dropped_ungrounded: number };
  stats: Record<string, any>; cached: boolean };

export type CompareResult = {
  papers: { paper_id: string; title: string | null; method: string; n_entities: number }[];
  dimensions: Record<string, Record<string, Evidenced[]>>;
  entities: { shared_by_all: string[]; pairs: { a: string; b: string; n_shared: number; jaccard: number; shared: string[] }[]; unique: Record<string, string[]> };
  tensions: null | { candidates: { paper_a: string; paper_b: string; a: Evidenced; b: Evidenced; shared_entities: string[]; contradiction_prob: number }[];
    pairs_checked: number; truncated: boolean; min_prob: number; caveat: string };
};

export async function fetchBlobUrl(path: string): Promise<string> {
  const r = await fetch(path, { headers: { Authorization: `Bearer ${token}` } });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return URL.createObjectURL(await r.blob());
}
export type Quoted = { text: string; quote: string | null };
export type Slide = { kind: string; title: string; bullets: Quoted[]; narration: string };
export type Turn = { speaker: "A" | "B"; text: string; quote?: string; start: number; end: number };
export type Brief = { title: string; note: string; shared_concepts: string[]; papers: { id: string; title: string; year: number | null; sections?: { heading: string; sentences: Quoted[] }[]; abstract: Quoted[]; research_question: Quoted[]; methodology: Quoted[];
  findings: Quoted[]; quantitative_results: Quoted[]; conclusions: Quoted[]; limitations: Quoted[]; future_work: Quoted[]; entities: string[] }[] };
export type StudioResult = { key: string; kind: string; title: string; note: string; cached: boolean; files: Record<string, string>; images?: string[]; renderer?: string; design?: { theme: { name: string; accents: string[] }; report: { provider: string | null; ai: boolean; headlines: number[]; notes: number[]; rejected: string[]; error?: string } }; fluent?: boolean; fluent_note?: string; fluent_stats?: { accepted: number; total: number }; brief?: Brief; mindmap?: GraphData; slides?: Slide[]; transcript?: Turn[]; duration_s?: number };
