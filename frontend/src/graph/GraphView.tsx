import { useEffect, useRef } from "react";
import cytoscape from "cytoscape";
import type { GraphData, GNode } from "../api";

export const DOMAIN_COLOR: Record<string, string> = { physics: "#60a5fa", chemistry: "#f59e0b", biology: "#34d399", ai_cs: "#c084fc", interdisciplinary: "#f472b6", other: "#94a3b8" };
const KIND_COLOR: Record<string, string> = { entity: "#38bdf8", finding: "#a3e635", limitation: "#fb7185", root: "#f8fafc", branch: "#fbbf24", leaf: "#94a3b8" };
const color = (n: GNode) => n.kind === "paper" ? DOMAIN_COLOR[n.domain ?? "other"] ?? "#94a3b8" : KIND_COLOR[n.kind] ?? "#64748b";

export default function GraphView({ data, onSelect, cyRef, highlight, layout = "cose" }: { layout?: "cose" | "breadthfirst"; data: GraphData; onSelect: (n: GNode | null) => void; cyRef: React.MutableRefObject<cytoscape.Core | null>; highlight?: string }) {
  const el = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!el.current) return;
    const cy = cytoscape({
      container: el.current, wheelSensitivity: 0.25,
      elements: [
        ...data.nodes.map(n => ({ data: { ...n, color: color(n), short: n.label.length > 28 ? n.label.slice(0, 27) + "…" : n.label } })),
        ...data.edges.map((e, i) => ({ data: { id: `e${i}`, ...e, name: e.kind === "semantic" ? `${e.rel} (semantic ${e.score?.toFixed(2)})` : e.rel } }))],
      style: [
        { selector: "node", style: { "background-color": "data(color)", label: "data(short)", color: "#d6dbe6", "font-size": 9, "text-valign": "bottom", "text-margin-y": 3, width: 16, height: 16 } },
        { selector: "node[kind = 'paper']", style: { shape: "round-rectangle", width: 22, height: 22 } },
        { selector: "node[kind = 'finding'], node[kind = 'limitation']", style: { shape: "diamond" } },
        { selector: "node[kind = 'leaf']", style: { "text-wrap": "wrap", "text-max-width": "150px", "font-size": 10 } },
        { selector: "edge", style: { width: 1.2, "line-color": "#475569", "target-arrow-color": "#475569", "target-arrow-shape": "triangle", "curve-style": "bezier", "arrow-scale": 0.7, opacity: 0.8 } },
        { selector: "edge[kind = 'semantic']", style: { "line-style": "dashed", "line-color": "#818cf8", "target-arrow-shape": "none" } },
        { selector: "edge[kind = 'citation']", style: { width: 2.5, "line-color": "#fbbf24", "target-arrow-color": "#fbbf24" } },
        { selector: ":selected", style: { "border-width": 3, "border-color": "#fff" } },
        { selector: ".dim", style: { opacity: 0.12 } }],
      layout: (layout === "breadthfirst" ? { name: "breadthfirst", directed: true, circle: true, spacingFactor: 1.25, roots: "#root", animate: false } : { name: "cose", animate: false, nodeRepulsion: () => 9000, idealEdgeLength: () => 70, randomize: true }) as any });
    cy.on("tap", "node", e => onSelect(e.target.data() as GNode));
    cy.on("tap", e => { if (e.target === cy) onSelect(null); });
    cyRef.current = cy;
    return () => { cy.destroy(); cyRef.current = null; };
  }, [data, layout]);
  useEffect(() => {
    const cy = cyRef.current; if (!cy) return;
    cy.elements().removeClass("dim");
    const q = (highlight ?? "").trim().toLowerCase();
    if (q) { const m = cy.nodes().filter(n => String(n.data("label")).toLowerCase().includes(q)); cy.elements().not(m.union(m.neighborhood())).addClass("dim"); if (m.length) cy.animate({ fit: { eles: m, padding: 60 }, duration: 250 }); }
  }, [highlight, data]);
  return <div ref={el} className="w-full h-[560px] rounded-xl border border-slate-800 bg-slate-950" role="img" aria-label="Knowledge graph" />;
}
