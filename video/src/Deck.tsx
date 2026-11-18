import { AbsoluteFill, Audio, Series, staticFile, useCurrentFrame, useVideoConfig, interpolate, spring, random } from "remotion";
import React from "react";

export type Item = { text: string; quote?: string | null };
export type Stat = { display: string; value: number; decimals: number; unit: string; label: string };
export type Slide = { kind: "title" | "quote" | "cards" | "steps" | "stats" | "concepts" | "split" | "sources"; title: string; accent?: number; frames: number; audio?: string | null;
  items?: Item[]; steps?: { label: string; text: string }[]; stats?: Stat[]; concepts?: string[]; center?: string; left?: Item[]; right?: Item[]; leftTitle?: string; rightTitle?: string;
  captions: { text: string; from: number; to: number }[]; n?: number; total?: number; subtitle?: string; kicker?: string };
export type Theme = { bg: string; accents: string[] };
export type DeckProps = { slides: Slide[]; fps: number; withAudio?: boolean; theme?: Theme };

const ACC = ["#38bdf8", "#a78bfa", "#34d399", "#fbbf24", "#fb7185"];
const FONT = "'Helvetica Neue', Helvetica, Arial, sans-serif";
const fs = (t: string) => (t.length < 90 ? 46 : t.length < 170 ? 38 : t.length < 260 ? 32 : 27);

const useSpring = (delay = 0, damping = 18) => { const f = useCurrentFrame(); const { fps } = useVideoConfig(); return spring({ frame: f - delay, fps, config: { damping, stiffness: 110 } }); };

function Backdrop({ accent, bg }: { accent: string; bg: string }) {
  const f = useCurrentFrame();
  return (<AbsoluteFill style={{ background: bg, overflow: "hidden" }}>
    {[0, 1, 2].map(i => <div key={i} style={{ position: "absolute", width: 900, height: 900, borderRadius: "50%", filter: "blur(160px)", opacity: 0.22, background: i === 1 ? "#6366f1" : accent,
      left: 300 + Math.sin(f / 70 + i * 2) * 500 + i * 380 - 400, top: 120 + Math.cos(f / 90 + i * 3) * 260 + i * 120 - 300 }} />)}
    <AbsoluteFill style={{ backgroundImage: "linear-gradient(rgba(255,255,255,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.035) 1px,transparent 1px)", backgroundSize: "80px 80px" }} />
    {Array.from({ length: 26 }).map((_, i) => { const x = random(`x${i}`) * 1920, sp = 0.25 + random(`s${i}`) * 0.7, y = ((random(`y${i}`) * 1200 - f * sp * 1.4) % 1200 + 1200) % 1200 - 60;
      return <div key={i} style={{ position: "absolute", left: x, top: y, width: 5 + random(`z${i}`) * 7, height: 5 + random(`z${i}`) * 7, borderRadius: "50%", background: accent, opacity: 0.18 + random(`o${i}`) * 0.25 }} />; })}
  </AbsoluteFill>);
}

function Heading({ title, accent, n, total, kicker }: { title: string; accent: string; n?: number; total?: number; kicker?: string }) {
  const s = useSpring(0);
  return (<div style={{ position: "absolute", left: 110, top: kicker ? 84 : 70, right: 110, opacity: s, transform: `translateY(${(1 - s) * -30}px)` }}>
    {kicker && <div style={{ position: "absolute", top: -42, left: 36, right: 160, fontSize: 25, color: accent, fontWeight: 700, lineHeight: 1.2, maxHeight: 62, overflow: "hidden" }}>{kicker}</div>}
    <div style={{ display: "flex", alignItems: "center", gap: 22 }}>
      <div style={{ width: 14, height: 70, borderRadius: 7, background: accent }} />
      <div style={{ fontSize: title.length > 48 ? 54 : 66, fontWeight: 800, color: "#f1f5f9", lineHeight: 1.1, letterSpacing: -1 }}>{title}</div>
      {n ? <div style={{ marginLeft: "auto", fontSize: 28, color: "#94a3b8", fontVariantNumeric: "tabular-nums" }}>{n} / {total}</div> : null}</div></div>);
}

function Title({ s, accent }: { s: Slide; accent: string }) {
  const f = useCurrentFrame(); const words = s.title.split(" ");
  return (<AbsoluteFill style={{ justifyContent: "center", padding: "0 160px" }}>
    <svg width="900" height="900" style={{ position: "absolute", right: -120, top: 90, opacity: 0.55 }} viewBox="-450 -450 900 900">
      {[150, 250, 350].map((r, i) => <circle key={i} r={r} fill="none" stroke={accent} strokeWidth={2 + (i === 1 ? 2 : 0)} strokeDasharray={`${40 + i * 30} ${30 + i * 20}`} transform={`rotate(${f * (i % 2 ? -0.5 : 0.7) + i * 40})`} opacity={0.35 + i * 0.2} />)}
      {[0, 1, 2, 3, 4].map(i => { const a = f / 40 + i * 1.26; return <circle key={i} cx={Math.cos(a) * (150 + (i % 3) * 100)} cy={Math.sin(a) * (150 + (i % 3) * 100)} r={11} fill={accent} />; })}</svg>
    <div style={{ fontSize: 22, letterSpacing: 8, color: accent, fontWeight: 700, marginBottom: 34, opacity: interpolate(f, [0, 20], [0, 1], { extrapolateRight: "clamp" }) }}>RESEARCH OVERVIEW</div>
    <div style={{ display: "flex", flexWrap: "wrap", gap: "0 24px", maxWidth: 1200 }}>{words.map((w, i) => { const sp = spring({ frame: f - 8 - i * 4, fps: 30, config: { damping: 16 } });
      return <span key={i} style={{ fontSize: words.length > 12 ? 70 : 96, fontWeight: 800, color: "#f8fafc", lineHeight: 1.12, letterSpacing: -2, opacity: sp, transform: `translateY(${(1 - sp) * 50}px)` }}>{w}</span>; })}</div>
    <div style={{ marginTop: 50, fontSize: (s.subtitle ?? "").length > 120 ? 26 : 30, color: "#94a3b8", maxWidth: 1250, lineHeight: 1.4, opacity: interpolate(f, [30, 55], [0, 1], { extrapolateRight: "clamp" }) }}>{s.subtitle ?? "Built from the paper's own text"}</div>
  </AbsoluteFill>);
}

function Quote({ s, accent }: { s: Slide; accent: string }) {
  const bar = useSpring(4); const tot = (s.items ?? []).slice(0, 3).reduce((a, i) => a + i.text.length, 0); const qs = tot < 260 ? 46 : tot < 480 ? 40 : tot < 700 ? 35 : 30;
  return (<AbsoluteFill style={{ padding: "230px 170px 130px 170px", justifyContent: "center" }}>
    <div style={{ position: "absolute", left: 110, top: 250, fontSize: 280, lineHeight: 1, color: accent, opacity: 0.35, fontFamily: "Georgia, serif" }}>“</div>
    <div style={{ borderLeft: `10px solid ${accent}`, paddingLeft: 50, transformOrigin: "top", transform: `scaleY(${bar})` }}>
      {(s.items ?? []).slice(0, 3).map((it, i) => { const sp = useSpring(10 + i * 14); return <p key={i} style={{ fontSize: qs, color: i ? "#e2e8f0" : "#f8fafc", lineHeight: 1.38, margin: "0 0 26px", opacity: sp, transform: `translateX(${(1 - sp) * 40}px)` }}>{it.text}</p>; })}</div>
  </AbsoluteFill>);
}

function Cards({ s, accent }: { s: Slide; accent: string }) {
  const items = (s.items ?? []).slice(0, 3); const mx = Math.max(...items.map(i => i.text.length), 1); const cs = (mx < 140 ? 40 : mx < 220 ? 35 : mx < 320 ? 31 : 27) - (items.length > 2 ? 3 : 0);
  return (<AbsoluteFill style={{ padding: "250px 110px 110px", flexDirection: "row", gap: 40, alignItems: "center" }}>
    {items.map((it, i) => { const sp = useSpring(8 + i * 10); return (<div key={i} style={{ flex: 1, borderRadius: 32, padding: "40px 38px", background: "linear-gradient(160deg,rgba(255,255,255,.09),rgba(255,255,255,.03))", border: "1px solid rgba(255,255,255,.14)",
      boxShadow: `0 30px 80px -30px ${accent}55`, opacity: sp, transform: `translateY(${(1 - sp) * 90}px) scale(${0.94 + sp * 0.06})` }}>
      <div style={{ width: 76, height: 76, borderRadius: "50%", background: accent, color: "#04111f", fontSize: 40, fontWeight: 800, display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 28 }}>{i + 1}</div>
      <div style={{ fontSize: cs, color: "#e2e8f0", lineHeight: 1.4 }}>{it.text}</div></div>); })}</AbsoluteFill>);
}

function Steps({ s, accent }: { s: Slide; accent: string }) {
  const st = (s.steps ?? []).slice(0, 3); const f = useCurrentFrame();
  return (<AbsoluteFill style={{ padding: "250px 110px 110px", flexDirection: "row", alignItems: "center" }}>
    {st.map((x, i) => { const sp = useSpring(6 + i * 16); const line = interpolate(f, [20 + i * 16, 38 + i * 16], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
      return (<React.Fragment key={i}>
        <div style={{ flex: 1, borderRadius: 30, padding: "38px 36px", background: i === 0 ? `${accent}22` : "rgba(255,255,255,.06)", border: `2px solid ${i === 0 ? accent : "rgba(255,255,255,.16)"}`, opacity: sp, transform: `scale(${0.9 + sp * 0.1})` }}>
          <div style={{ display: "inline-block", padding: "8px 22px", borderRadius: 40, background: accent, color: "#04111f", fontWeight: 800, fontSize: 24, letterSpacing: 2, marginBottom: 26 }}>{x.label.toUpperCase()}</div>
          <div style={{ fontSize: fs(x.text) - 6, color: "#e2e8f0", lineHeight: 1.4 }}>{x.text}</div></div>
        {i < st.length - 1 && <div style={{ width: 120, display: "flex", alignItems: "center", justifyContent: "center" }}><svg width="110" height="60" viewBox="0 0 110 60"><line x1="6" y1="30" x2={6 + 80 * line} y2="30" stroke={accent} strokeWidth="6" strokeLinecap="round" /><polygon points="86,12 108,30 86,48" fill={accent} opacity={line} /></svg></div>}</React.Fragment>); })}</AbsoluteFill>);
}

function Stats({ s, accent }: { s: Slide; accent: string }) {
  const f = useCurrentFrame(); const st = (s.stats ?? []).slice(0, 3);
  return (<AbsoluteFill style={{ padding: "250px 110px 110px", flexDirection: "row", gap: 40, alignItems: "center" }}>
    {st.map((x, i) => { const sp = useSpring(6 + i * 12); const p = interpolate(f, [14 + i * 12, 54 + i * 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }); const v = x.value * (1 - Math.pow(1 - p, 3));
      const pct = x.unit === "%"; return (<div key={i} style={{ flex: 1, borderRadius: 32, padding: "44px 40px", background: "linear-gradient(160deg,rgba(255,255,255,.09),rgba(255,255,255,.03))", border: "1px solid rgba(255,255,255,.14)", opacity: sp, transform: `translateY(${(1 - sp) * 70}px)` }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}><span style={{ fontSize: 150, fontWeight: 800, color: accent, letterSpacing: -4, fontVariantNumeric: "tabular-nums", lineHeight: 1 }}>{v.toFixed(x.decimals)}</span><span style={{ fontSize: 52, color: "#94a3b8", fontWeight: 700 }}>{x.unit}</span></div>
        {pct && <div style={{ height: 16, borderRadius: 8, background: "rgba(255,255,255,.1)", margin: "28px 0 6px", overflow: "hidden" }}><div style={{ width: `${Math.min(100, x.value) * p}%`, height: "100%", background: accent, borderRadius: 8 }} /></div>}
        <div style={{ fontSize: x.label.length > 170 ? 24 : 28, color: "#cbd5e1", lineHeight: 1.4, marginTop: 24 }}>{x.label}</div></div>); })}</AbsoluteFill>);
}

function Concepts({ s, accent }: { s: Slide; accent: string }) {
  const f = useCurrentFrame(); const c = (s.concepts ?? []).slice(0, 10); const cx = 960, cy = 640, R = 330; const cs = useSpring(2);
  return (<AbsoluteFill>
    <svg width="1920" height="1080" style={{ position: "absolute" }}>{c.map((_, i) => { const a = (i / c.length) * Math.PI * 2 - Math.PI / 2, sp = spring({ frame: f - 10 - i * 4, fps: 30, config: { damping: 18 } });
      return <line key={i} x1={cx} y1={cy} x2={cx + Math.cos(a) * R * 1.35 * sp} y2={cy + Math.sin(a) * R * sp} stroke={accent} strokeOpacity={0.45} strokeWidth={3} />; })}</svg>
    <div style={{ position: "absolute", left: cx - 150, top: cy - 150, width: 300, height: 300, borderRadius: "50%", background: `radial-gradient(circle at 30% 30%, ${accent}, #1e1b4b)`, display: "flex", alignItems: "center", justifyContent: "center", textAlign: "center", fontSize: (s.center ?? "").length > 24 ? 26 : 34, fontWeight: 800, color: "#fff", padding: 30, transform: `scale(${cs})`, boxShadow: `0 0 120px ${accent}88` }}>{s.center ?? "Key concepts"}</div>
    {c.map((t, i) => { const a = (i / c.length) * Math.PI * 2 - Math.PI / 2, sp = spring({ frame: f - 10 - i * 4, fps: 30, config: { damping: 14 } }); const fl = Math.sin(f / 22 + i) * 9;
      return <div key={i} style={{ position: "absolute", left: cx + Math.cos(a) * R * 1.35 * sp, top: cy + Math.sin(a) * R * sp + fl, transform: "translate(-50%,-50%)", padding: "16px 30px", borderRadius: 60, background: "rgba(15,23,42,.92)", border: `2px solid ${accent}`, color: "#e2e8f0", fontSize: 32, fontWeight: 600, whiteSpace: "nowrap", opacity: sp, maxWidth: 520, overflow: "hidden", textOverflow: "ellipsis" }}>{t}</div>; })}</AbsoluteFill>);
}

function Split({ s, accent }: { s: Slide; accent: string }) {
  const col = (title: string, items: Item[], color: string, icon: string, d: number) => { const sp = useSpring(d); const tot = items.slice(0, 3).reduce((a, i) => a + i.text.length, 0); const ss = tot < 200 ? 36 : tot < 380 ? 31 : tot < 560 ? 27 : 24;
    return (<div style={{ flex: 1, borderRadius: 32, padding: "40px 44px", background: `${color}14`, border: `2px solid ${color}66`, opacity: sp, transform: `translateY(${(1 - sp) * 70}px)` }}>
      <div style={{ display: "flex", alignItems: "center", gap: 20, marginBottom: 26 }}><div style={{ fontSize: 54 }}>{icon}</div><div style={{ fontSize: 38, fontWeight: 800, color }}>{title}</div></div>
      {items.slice(0, 3).map((it, i) => <p key={i} style={{ fontSize: ss, color: "#e2e8f0", lineHeight: 1.4, margin: "0 0 20px" }}>{it.text}</p>)}</div>); };
  return (<AbsoluteFill style={{ padding: "250px 110px 110px", flexDirection: "row", gap: 40, alignItems: "center" }}>{col(s.leftTitle ?? "Limitations", s.left ?? [], "#fb7185", "⚠", 6)}{col(s.rightTitle ?? "Future work", s.right ?? [], accent, "➜", 18)}</AbsoluteFill>);
}

function Sources({ s, accent }: { s: Slide; accent: string }) {
  return (<AbsoluteFill style={{ padding: "280px 160px 130px", gap: 26 }}>{(s.items ?? []).slice(0, 6).map((it, i) => { const sp = useSpring(6 + i * 8);
    return <div key={i} style={{ display: "flex", alignItems: "center", gap: 28, opacity: sp, transform: `translateX(${(1 - sp) * 60}px)` }}><div style={{ width: 62, height: 62, borderRadius: 16, background: accent, color: "#04111f", fontWeight: 800, fontSize: 32, display: "flex", alignItems: "center", justifyContent: "center" }}>{i + 1}</div><div style={{ fontSize: 36, color: "#e2e8f0" }}>{it.text}</div></div>; })}</AbsoluteFill>);
}

function Captions({ s }: { s: Slide }) {
  const f = useCurrentFrame(); const c = s.captions.find(x => f >= x.from && f < x.to); if (!c) return null;
  const o = Math.min(interpolate(f, [c.from, c.from + 8], [0, 1], { extrapolateRight: "clamp" }), interpolate(f, [c.to - 6, c.to], [1, 0], { extrapolateLeft: "clamp" }));
  return <div style={{ position: "absolute", left: 160, right: 160, bottom: 46, textAlign: "center", fontSize: 32, color: "#fff", opacity: o }}><span style={{ background: "rgba(2,6,23,.78)", padding: "10px 22px", borderRadius: 14, lineHeight: 1.6, boxDecorationBreak: "clone", WebkitBoxDecorationBreak: "clone" }}>{c.text}</span></div>;
}

function Scene({ s, theme }: { s: Slide; theme?: Theme }) {
  const f = useCurrentFrame(); const pal = theme?.accents?.length ? theme.accents : ACC; const accent = pal[(s.accent ?? 0) % pal.length];
  const fade = Math.min(interpolate(f, [0, 8], [0, 1], { extrapolateRight: "clamp" }), interpolate(f, [s.frames - 8, s.frames], [1, 0], { extrapolateLeft: "clamp" }));
  const B = { title: Title, quote: Quote, cards: Cards, steps: Steps, stats: Stats, concepts: Concepts, split: Split, sources: Sources }[s.kind] ?? Cards;
  return (<AbsoluteFill style={{ fontFamily: FONT }}><Backdrop accent={accent} bg={theme?.bg ?? "#070a12"} />
    <AbsoluteFill style={{ opacity: fade }}>{s.kind !== "title" && <Heading title={s.title} accent={accent} n={s.n} total={s.total} kicker={s.kicker} />}<B s={s} accent={accent} /><Captions s={s} />
      <div style={{ position: "absolute", left: 0, bottom: 0, height: 8, width: `${(f / Math.max(1, s.frames)) * 100}%`, background: accent }} /></AbsoluteFill>
    {s.audio ? <Audio src={staticFile(s.audio)} /> : null}</AbsoluteFill>);
}

export const Deck: React.FC<DeckProps> = ({ slides, theme }) => (<Series>{slides.map((s, i) => <Series.Sequence key={i} durationInFrames={s.frames}><Scene s={s} theme={theme} /></Series.Sequence>)}</Series>);
