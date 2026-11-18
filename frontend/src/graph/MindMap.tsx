import { useEffect, useMemo, useRef, useState } from "react";
import type { GraphData, GNode } from "../api";

// NotebookLM-style mind map: horizontal tree (root left → leaves right), pill nodes, curved connectors,
// click a node's chevron to expand/collapse, drag to pan, wheel to zoom.
type T = { id: string; label: string; kind: string; quote?: string; children: T[]; color: string; depth: number; raw: GNode };
const BRANCH_COLORS: Record<string, string> = { summary: "#60a5fa", conclusions: "#f59e0b", "research question": "#38bdf8", methodology: "#a78bfa", findings: "#34d399", results: "#fbbf24", limitations: "#fb7185", "future work": "#2dd4bf", "key concepts": "#f472b6", "shared concepts": "#f472b6" };
const PALETTE = ["#38bdf8", "#a78bfa", "#34d399", "#fbbf24", "#fb7185", "#2dd4bf", "#f472b6"];
const W: Record<string, number> = { root: 280, paper: 270, branch: 190, leaf: 380, entity: 200 };
const MINH: Record<string, number> = { root: 80, paper: 60, branch: 48, leaf: 52, entity: 42 };
// node height grows with its (never truncated) text
const nodeH = (t: { kind: string; label: string }) => { const cpl = Math.floor(((W[t.kind] ?? 200) - (t.kind === "leaf" ? 28 : 60)) / (t.kind === "root" ? 9.5 : t.kind === "leaf" ? 6.6 : 8)); const lines = Math.ceil(t.label.length / Math.max(8, cpl)); return Math.max(MINH[t.kind] ?? 48, lines * (t.kind === "leaf" ? 18 : 22) + (t.kind === "leaf" ? 22 : 30)); };
const GAP_X = 80, GAP_Y = 12;

function buildTree(d: GraphData): T {
  const by = new Map(d.nodes.map(n => [n.id, n])); const kids = new Map<string, string[]>();
  d.edges.forEach(e => kids.set(e.source, [...(kids.get(e.source) ?? []), e.target]));
  let pi = 0;
  const mk = (id: string, depth: number, color?: string): T => {
    const n = by.get(id)!; const c = color ?? (depth === 0 ? "#e2e8f0" : BRANCH_COLORS[n.label.toLowerCase()] ?? PALETTE[pi++ % PALETTE.length]);
    const col = n.kind === "paper" ? PALETTE[pi++ % PALETTE.length] : c;
    return { id, label: n.label, kind: n.kind, quote: n.quote, depth, raw: n, color: col, children: (kids.get(id) ?? []).map(k => mk(k, depth + 1, depth === 0 ? undefined : col)) };
  };
  return mk("root", 0);
}

type P = { t: T; x: number; y: number; w: number; h: number; parent?: P };
function layout(root: T, open: Set<string>) {
  const vis = (t: T) => (open.has(t.id) ? t.children : []);
  const sub = (t: T): number => { const k = vis(t); return k.length ? Math.max(nodeH(t), k.reduce((a, c) => a + sub(c), 0) + GAP_Y * (k.length - 1)) : nodeH(t); };
  const out: P[] = [];
  const place = (t: T, x: number, top: number, parent?: P) => {
    const k = vis(t), h = nodeH(t), w = W[t.kind] ?? 200, total = sub(t);
    const p: P = { t, x, y: top + total / 2 - h / 2, w, h, parent }; out.push(p);
    let cy = top + (total - (k.reduce((a, c) => a + sub(c), 0) + GAP_Y * Math.max(0, k.length - 1))) / 2;
    k.forEach(c => { place(c, x + w + GAP_X, cy, p); cy += sub(c) + GAP_Y; });
  };
  place(root, 0, 0);
  return out;
}

export default function MindMap({ data, onSelect }: { data: GraphData; onSelect?: (n: GNode | null) => void }) {
  const tree = useMemo(() => buildTree(data), [data]);
  const initial = useMemo(() => { const s = new Set<string>(); const w = (t: T) => { s.add(t.id); t.children.forEach(w); }; w(tree); return s; }, [tree]);   // everything open by default
  const [open, setOpen] = useState<Set<string>>(initial); const [sel, setSel] = useState<string | null>(null); const [hover, setHover] = useState<string | null>(null);
  const [view, setView] = useState({ x: 40, y: 0, k: 1 }); const box = useRef<HTMLDivElement>(null); const drag = useRef<{ x: number; y: number; vx: number; vy: number } | null>(null);
  useEffect(() => { setOpen(initial); setSel(null); }, [initial]);
  const nodes = useMemo(() => layout(tree, open), [tree, open]);
  const bounds = useMemo(() => ({ w: Math.max(...nodes.map(n => n.x + n.w)), h: Math.max(...nodes.map(n => n.y + n.h)), minY: Math.min(...nodes.map(n => n.y)) }), [nodes]);
  const fit = () => { const el = box.current; if (!el) return; const k = Math.max(0.4, Math.min(1, (el.clientWidth - 60) / bounds.w, (el.clientHeight - 40) / (bounds.h - bounds.minY))); setView({ k, x: 30, y: (el.clientHeight - (bounds.h - bounds.minY) * k) / 2 - bounds.minY * k }); };
  useEffect(fit, [bounds.w, bounds.h]);
  const toggle = (id: string) => setOpen(o => { const n = new Set(o); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const all = () => { const s = new Set<string>(); const w = (t: T) => { s.add(t.id); t.children.forEach(w); }; w(tree); setOpen(s); };
  const onWheel = (e: React.WheelEvent) => { const r = box.current!.getBoundingClientRect(); const mx = e.clientX - r.left, my = e.clientY - r.top; const k = Math.max(0.3, Math.min(2, view.k * (e.deltaY < 0 ? 1.1 : 0.9)));
    setView(v => ({ k, x: mx - (mx - v.x) * (k / v.k), y: my - (my - v.y) * (k / v.k) })); };
  const active = useMemo(() => { const s = new Set<string>(); let p = nodes.find(n => n.t.id === (hover ?? sel)); while (p) { s.add(p.t.id); p = p.parent; } return s; }, [nodes, hover, sel]);

  return (<div className="rounded-2xl border border-slate-800 overflow-hidden" style={{ background: "radial-gradient(1200px 600px at 20% 10%, #111a2e 0%, #0a0f1a 60%)" }}>
    <div className="flex justify-end gap-1.5 text-xs p-3 pb-0">
      {[["Fit", fit], ["Expand all", all], ["Collapse", () => setOpen(new Set(["root"]))], ["＋", () => setView(v => ({ ...v, k: Math.min(2, v.k * 1.2) }))], ["－", () => setView(v => ({ ...v, k: Math.max(0.3, v.k / 1.2) }))]].map(([l, f]) =>
        <button key={l as string} onClick={f as () => void} className="px-2.5 py-1 rounded-full bg-slate-900/80 border border-slate-700 text-slate-300 hover:border-slate-500">{l as string}</button>)}</div>
    <div ref={box} className="relative h-[720px] cursor-grab active:cursor-grabbing touch-none select-none" onWheel={onWheel}
      onPointerDown={e => { if ((e.target as HTMLElement).closest("[data-node]")) return; drag.current = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y }; (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId); }}
      onPointerMove={e => { const d = drag.current; if (d) setView(v => ({ ...v, x: d.vx + e.clientX - d.x, y: d.vy + e.clientY - d.y })); }} onPointerUp={() => (drag.current = null)}>
      <div style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.k})`, transformOrigin: "0 0", position: "absolute", transition: drag.current ? "none" : "transform .12s" }}>
        <svg width={bounds.w + 40} height={bounds.h + 40} style={{ position: "absolute", overflow: "visible" }}>
          {nodes.filter(n => n.parent).map(n => { const p = n.parent!; const x1 = p.x + p.w, y1 = p.y + p.h / 2, x2 = n.x, y2 = n.y + n.h / 2, mx = (x1 + x2) / 2; const on = active.has(n.t.id);
            return <path key={n.t.id} d={`M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`} fill="none" stroke={n.t.color} strokeWidth={on ? 3 : 2} strokeOpacity={on ? 0.95 : 0.4} strokeLinecap="round" />; })}</svg>
        {nodes.map(({ t, x, y, w, h }) => { const isSel = sel === t.id; const has = t.children.length > 0; const root = t.kind === "root", leaf = t.kind === "leaf";
          return (<div key={t.id} data-node onMouseEnter={() => setHover(t.id)} onMouseLeave={() => setHover(null)} onClick={() => { setSel(t.id); onSelect?.(t.raw); }}
            style={{ position: "absolute", left: x, top: y, width: w, height: h, borderRadius: root ? 28 : leaf ? 16 : t.kind === "paper" ? 28 : 999, padding: leaf ? "10px 14px" : "0 18px", display: "flex", alignItems: "center", gap: 10, boxSizing: "border-box",
              background: root ? "linear-gradient(135deg,#38bdf8,#6366f1)" : leaf ? "rgba(255,255,255,.045)" : `${t.color}1f`, border: `1.5px solid ${root ? "transparent" : isSel ? t.color : leaf ? "rgba(255,255,255,.12)" : `${t.color}99`}`,
              boxShadow: isSel ? `0 0 0 3px ${t.color}44, 0 10px 30px -10px ${t.color}` : root ? "0 14px 40px -14px #6366f1" : "none", color: root ? "#fff" : "#e2e8f0", cursor: "pointer", transition: "box-shadow .15s, border-color .15s" }}>
            {!root && !leaf && <span style={{ width: 10, height: 10, borderRadius: "50%", background: t.color, flex: "none" }} />}
            <span style={{ fontSize: root ? 17 : leaf ? 13 : 14.5, fontWeight: root || !leaf ? 650 : 400, lineHeight: 1.35, flex: 1, overflowWrap: "anywhere" }}>{t.label}</span>
            {has && <button aria-label={open.has(t.id) ? "Collapse" : "Expand"} onClick={e => { e.stopPropagation(); toggle(t.id); }} style={{ flex: "none", width: 26, height: 26, borderRadius: "50%", border: `1.5px solid ${root ? "#fff8" : t.color}`, background: "#0a0f1a", color: root ? "#fff" : t.color, fontSize: 12, lineHeight: 1, cursor: "pointer", position: "absolute", right: -13 }}>{open.has(t.id) ? "‹" : t.children.length}</button>}
          </div>); })}
      </div></div></div>);
}
