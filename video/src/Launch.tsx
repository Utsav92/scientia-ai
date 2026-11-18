import React from "react";
import { AbsoluteFill, Audio, Easing, Img, OffthreadVideo, Sequence, interpolate, random, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";

// SCIENTIA AI launch film. Apple-style: black stage, large light typography, generous space, slow springs, camera moves.
export type Zoom = { t: number; s: number; x: number; y: number };
export type Turn = { speaker: "A" | "B"; text: string; start: number; end: number };
export type Scene =
  | { type: "intro"; frames: number }
  | { type: "clip"; frames: number; clip: string; head: string; sub: string; pill: string; zooms: Zoom[]; cardFrames: number; accent: string }
  | { type: "audio"; frames: number; file: string; env: number[]; turns: Turn[]; head: string }
  | { type: "wall"; frames: number; slides: string[]; head: string; sub: string }
  | { type: "video"; frames: number; file: string; head: string; sub: string; from: number }
  | { type: "outro"; frames: number };
export type LaunchProps = { scenes: Scene[]; music: string; duck: [number, number][] };

const FONT = "system-ui, -apple-system, 'SF Pro Display', 'Helvetica Neue', Helvetica, Arial, sans-serif";
const GRAD = "linear-gradient(100deg,#6ec1ff 0%,#a78bfa 45%,#ff7ab6 100%)";
const ease = Easing.bezier(0.22, 0.8, 0.2, 1);

const Words: React.FC<{ text: string; size: number; delay?: number; weight?: number; gradFrom?: number; color?: string; align?: "center" | "left"; lh?: number }> = ({ text, size, delay = 0, weight = 600, gradFrom = 99, color = "#f5f5f7", align = "center", lh = 1.05 }) => {
  const f = useCurrentFrame(); const w = text.split(" ");
  return (<div style={{ display: "flex", flexWrap: "wrap", justifyContent: align === "center" ? "center" : "flex-start", columnGap: size * 0.26, rowGap: 0 }}>{w.map((x, i) => {
    const p = interpolate(f - delay - i * 5, [0, 26], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
    const g = i >= gradFrom; return <span key={i} style={{ fontSize: size, fontWeight: weight, letterSpacing: -size * 0.03, lineHeight: lh, opacity: p, transform: `translateY(${(1 - p) * size * 0.35}px)`, filter: `blur(${(1 - p) * 14}px)`,
      color: g ? "transparent" : color, backgroundImage: g ? GRAD : undefined, backgroundSize: "200% 100%", backgroundPosition: `${(f * 0.4) % 200}% 0`, WebkitBackgroundClip: g ? "text" : undefined, backgroundClip: g ? "text" : undefined, display: "inline-block" }}>{x}</span>; })}</div>);
};

const Glow: React.FC<{ color?: string; y?: number; o?: number }> = ({ color = "#3b6cff", y = 1100, o = 0.22 }) => {
  const f = useCurrentFrame();
  return (<AbsoluteFill style={{ background: "#000" }}><div style={{ position: "absolute", left: 960 - 900, top: y - 500 + Math.sin(f / 90) * 14, width: 1800, height: 1000, borderRadius: "50%", background: `radial-gradient(closest-side, ${color}, transparent)`, opacity: o, filter: "blur(40px)" }} />
    {Array.from({ length: 36 }).map((_, i) => <div key={i} style={{ position: "absolute", left: random(`gx${i}`) * 1920, top: ((random(`gy${i}`) * 1200 - f * (0.1 + random(`gs${i}`) * 0.25)) % 1100 + 1100) % 1100, width: 2 + random(`gz${i}`) * 3, height: 2 + random(`gz${i}`) * 3, borderRadius: "50%", background: "#fff", opacity: 0.08 + random(`go${i}`) * 0.3 }} />)}</AbsoluteFill>);
};

const Moon: React.FC<{ rise: number }> = ({ rise }) => (<div style={{ position: "absolute", left: 960 - 1100, top: 1080 - 380 * rise + 500 * (1 - rise), width: 2200, height: 2200, borderRadius: "50%", overflow: "hidden",
  background: "radial-gradient(circle at 50% 12%, #f4f6ff 0%, #c9d2ee 14%, #6c7aa8 38%, #232b49 62%, #070a16 80%)", boxShadow: "0 -30px 160px 20px rgba(120,160,255,.35), inset 0 40px 120px rgba(255,255,255,.28)" }}>
  {[[640, 140, 150], [1180, 90, 110], [900, 300, 90], [1500, 220, 140], [420, 330, 80], [1330, 420, 70]].map(([x, y, r], i) => <div key={i} style={{ position: "absolute", left: x, top: y, width: r, height: r * 0.8, borderRadius: "50%", background: "radial-gradient(circle at 40% 35%, rgba(60,70,110,.35), rgba(255,255,255,.08) 70%)", opacity: 0.8 }} />)}</div>);

function Intro({ frames }: { frames: number }) {
  const f = useCurrentFrame(); const rise = interpolate(f, [0, 150], [0, 1], { extrapolateRight: "clamp", easing: Easing.bezier(0.16, 1, 0.3, 1) });
  const out = interpolate(f, [frames - 14, frames], [1, 0], { extrapolateLeft: "clamp" });
  return (<AbsoluteFill><Glow y={1000} o={0.1} /><Moon rise={rise} /><AbsoluteFill style={{ justifyContent: "center", alignItems: "center", flexDirection: "column", fontFamily: FONT, opacity: out, paddingBottom: 220 }}>
    <div style={{ fontSize: 30, letterSpacing: 10, fontWeight: 600, color: "#a1a1aa", marginBottom: 46, opacity: interpolate(f, [10, 40], [0, 1], { extrapolateRight: "clamp" }) }}>INTRODUCING SCIENTIA AI</div>
    <Words text="Research," size={210} delay={36} /><Words text="understood." size={210} delay={58} gradFrom={0} /></AbsoluteFill></AbsoluteFill>);
}

const Pill: React.FC<{ text: string; delay: number; accent: string }> = ({ text, delay, accent }) => {
  const f = useCurrentFrame(); const { fps } = useVideoConfig(); const s = spring({ frame: f - delay, fps, config: { damping: 22, stiffness: 120 } });
  return <div style={{ position: "absolute", left: 0, right: 0, bottom: 34, display: "flex", justifyContent: "center", opacity: s, transform: `translateY(${(1 - s) * 30}px)` }}>
    <div style={{ fontFamily: FONT, fontSize: 30, fontWeight: 500, color: "#f5f5f7", padding: "16px 34px", borderRadius: 60, background: "rgba(28,28,32,.78)", backdropFilter: "blur(30px)", border: `1px solid ${accent}66`, boxShadow: `0 20px 60px -20px ${accent}` }}>{text}</div></div>;
};

const FW = 1560, CH = 46, FH = Math.round(FW / 1.6);   // window content is 2160x1350 (1.6:1)
function Window({ children, scale = 1, opacity = 1, tilt = 0 }: { children: React.ReactNode; scale?: number; opacity?: number; tilt?: number }) {
  return (<div style={{ position: "absolute", left: (1920 - FW) / 2, top: (1080 - FH - CH) / 2 - 14, width: FW, height: FH + CH, borderRadius: 22, overflow: "hidden", background: "#0b0e14", opacity, transform: `perspective(2400px) rotateX(${tilt}deg) scale(${scale})`,
    boxShadow: "0 60px 160px -30px rgba(0,0,0,.9), 0 0 0 1px rgba(255,255,255,.12), 0 0 120px -10px rgba(80,130,255,.22)" }}>
    <div style={{ height: CH, background: "linear-gradient(#2a2a30,#1f1f24)", display: "flex", alignItems: "center", padding: "0 20px", gap: 10, borderBottom: "1px solid rgba(255,255,255,.08)" }}>
      {["#ff5f57", "#febc2e", "#28c840"].map(c => <div key={c} style={{ width: 14, height: 14, borderRadius: "50%", background: c }} />)}
      <div style={{ margin: "0 auto", fontFamily: FONT, fontSize: 17, color: "#9a9aa3", background: "#141418", padding: "6px 80px", borderRadius: 9 }}>scientia.ai</div><div style={{ width: 54 }} /></div>
    <div style={{ position: "relative", width: FW, height: FH, overflow: "hidden" }}>{children}</div></div>);
}

function zoomAt(f: number, fps: number, z: Zoom[]) {
  const t = f / fps; if (!z.length) return { s: 1, x: 0.5, y: 0.5 };
  let a = z[0], b = z[0];
  for (let i = 0; i < z.length; i++) { if (z[i].t <= t) a = z[i]; if (z[i].t > t) { b = z[i]; break; } if (i === z.length - 1) b = z[i]; }
  if (a === b) return { s: a.s, x: a.x, y: a.y };
  const p = Easing.inOut(Easing.cubic)(Math.min(1, Math.max(0, (t - a.t) / (b.t - a.t))));
  return { s: a.s + (b.s - a.s) * p, x: a.x + (b.x - a.x) * p, y: a.y + (b.y - a.y) * p };
}

function ClipScene({ sc }: { sc: Extract<Scene, { type: "clip" }> }) {
  const f = useCurrentFrame(); const { fps } = useVideoConfig(); const cf = sc.cardFrames;
  const cardOut = interpolate(f, [cf - 16, cf + 6], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  const win = interpolate(f, [cf - 12, cf + 26], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  const fade = Math.min(interpolate(f, [0, 8], [0, 1], { extrapolateRight: "clamp" }), interpolate(f, [sc.frames - 10, sc.frames], [1, 0], { extrapolateLeft: "clamp" }));
  const z = zoomAt(Math.max(0, f - cf), fps, sc.zooms); const tx = Math.min(0, Math.max(FW - FW * z.s, FW / 2 - z.x * FW * z.s)), ty = Math.min(0, Math.max(FH - FH * z.s, FH / 2 - z.y * FH * z.s));
  return (<AbsoluteFill style={{ fontFamily: FONT, opacity: fade }}><Glow color={sc.accent} y={900} o={0.2 + 0.1 * win} />
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", flexDirection: "column", opacity: cardOut, transform: `scale(${1 + (1 - cardOut) * 0.06})`, filter: `blur(${(1 - cardOut) * 10}px)` }}>
      <Words text={sc.head} size={150} delay={4} gradFrom={sc.head.split(" ").length - 1} /><div style={{ height: 36 }} /><Words text={sc.sub} size={44} weight={400} color="#a1a1aa" delay={22} lh={1.2} /></AbsoluteFill>
    <Window scale={0.9 + 0.1 * win} opacity={win} tilt={(1 - win) * 6}>
      <div style={{ position: "absolute", left: 0, top: 0, width: FW, height: FH, transformOrigin: "0 0", transform: `translate(${tx}px, ${ty}px) scale(${z.s})` }}>
        <OffthreadVideo src={staticFile(`clips/${sc.clip}`)} style={{ width: FW, height: FH, objectFit: "cover" }} muted /></div></Window>
    <Sequence from={cf + 40}><Pill text={sc.pill} delay={0} accent={sc.accent} /></Sequence></AbsoluteFill>);
}

function AudioScene({ sc }: { sc: Extract<Scene, { type: "audio" }> }) {
  const f = useCurrentFrame(); const { fps } = useVideoConfig(); const t = Math.max(0, (f - 24) / fps);
  const fade = Math.min(interpolate(f, [0, 12], [0, 1], { extrapolateRight: "clamp" }), interpolate(f, [sc.frames - 14, sc.frames], [1, 0], { extrapolateLeft: "clamp" }));
  const idx = Math.max(0, sc.turns.findIndex(x => t >= x.start && t < x.end)); const cur = sc.turns[idx] ?? sc.turns[sc.turns.length - 1];
  const ei = Math.min(sc.env.length - 1, Math.max(0, f - 24)); const N = 72;
  return (<AbsoluteFill style={{ fontFamily: FONT, opacity: fade }}><Glow color="#7c5cff" y={820} o={0.28} />
    <div style={{ position: "absolute", top: 110, width: "100%", display: "flex", justifyContent: "center" }}><Words text={sc.head} size={120} gradFrom={2} /></div>
    <div style={{ position: "absolute", top: 400, left: 0, right: 0, height: 260, display: "flex", justifyContent: "center", alignItems: "center", gap: 9 }}>
      {Array.from({ length: N }).map((_, i) => { const c = Math.abs(i - N / 2) / (N / 2); const amp = (sc.env[Math.max(0, ei - Math.round(c * 9))] ?? 0) * (1 - c * 0.55); const h = 14 + amp * 250 * (0.55 + 0.45 * Math.sin(i * 0.7 + f / 5));
        return <div key={i} style={{ width: 11, height: h, borderRadius: 8, background: GRAD, opacity: 0.35 + amp * 0.65 }} />; })}</div>
    <div style={{ position: "absolute", top: 730, left: 220, right: 220, textAlign: "center" }}>
      <div style={{ fontSize: 24, letterSpacing: 6, fontWeight: 700, color: cur?.speaker === "A" ? "#6ec1ff" : "#ff7ab6", marginBottom: 20 }}>{cur ? `HOST ${cur.speaker}` : ""}</div>
      <div key={idx} style={{ fontSize: 46, fontWeight: 500, color: "#f5f5f7", lineHeight: 1.28, opacity: interpolate((f - 24) / fps - (cur?.start ?? 0), [0, 0.35], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>{cur?.text}</div></div>
    <Sequence from={24}><Audio src={staticFile(sc.file)} volume={1} /></Sequence></AbsoluteFill>);
}

function Wall({ sc }: { sc: Extract<Scene, { type: "wall" }> }) {
  const f = useCurrentFrame(); const n = sc.slides.length; const rot = interpolate(f, [0, sc.frames], [18, -18]);
  const fade = Math.min(interpolate(f, [0, 12], [0, 1], { extrapolateRight: "clamp" }), interpolate(f, [sc.frames - 14, sc.frames], [1, 0], { extrapolateLeft: "clamp" }));
  return (<AbsoluteFill style={{ fontFamily: FONT, opacity: fade }}><Glow color="#ff7a45" y={900} o={0.2} />
    <div style={{ position: "absolute", top: 90, width: "100%", display: "flex", flexDirection: "column", alignItems: "center", gap: 18 }}><Words text={sc.head} size={118} gradFrom={2} /><Words text={sc.sub} size={40} weight={400} color="#a1a1aa" delay={14} /></div>
    <div style={{ position: "absolute", left: 0, top: 360, width: 1920, height: 560, perspective: 2200 }}>
      <div style={{ position: "absolute", left: 960 - 330, top: 80, width: 660, height: 372, transformStyle: "preserve-3d", transform: `rotateY(${rot}deg)` }}>
        {sc.slides.map((s, i) => { const p = interpolate(f, [8 + i * 5, 34 + i * 5], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease }); const a = (i / n) * 360;
          return <Img key={i} src={staticFile(`slides/${s}`)} style={{ position: "absolute", width: 660, height: 372, borderRadius: 18, transform: `rotateY(${a}deg) translateZ(${820 * p}px)`, boxShadow: "0 30px 80px -20px rgba(0,0,0,.9), 0 0 0 1px rgba(255,255,255,.14)", opacity: p, backfaceVisibility: "hidden" }} />; })}</div></div>
    <Sequence from={50}><Pill text="Export to PowerPoint (.pptx) or PDF" delay={0} accent="#ff7a45" /></Sequence></AbsoluteFill>);
}

function VideoScene({ sc }: { sc: Extract<Scene, { type: "video" }> }) {
  const f = useCurrentFrame(); const cf = 60; const fade = Math.min(interpolate(f, [0, 8], [0, 1], { extrapolateRight: "clamp" }), interpolate(f, [sc.frames - 14, sc.frames], [1, 0], { extrapolateLeft: "clamp" }));
  const cardOut = interpolate(f, [cf - 16, cf + 6], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease }); const win = interpolate(f, [cf - 12, cf + 26], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  return (<AbsoluteFill style={{ fontFamily: FONT, opacity: fade }}><Glow color="#20c997" y={900} o={0.22} />
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", flexDirection: "column", opacity: cardOut, transform: `scale(${1 + (1 - cardOut) * 0.06})` }}><Words text={sc.head} size={150} gradFrom={1} /><div style={{ height: 36 }} /><Words text={sc.sub} size={44} weight={400} color="#a1a1aa" delay={20} /></AbsoluteFill>
    <Window scale={0.9 + 0.1 * win} opacity={win} tilt={(1 - win) * 6}><div style={{ width: FW, height: FH, background: "#000" }}><Sequence from={cf}><OffthreadVideo src={staticFile(sc.file)} startFrom={sc.from} style={{ width: FW, height: FH, objectFit: "contain" }} volume={1} /></Sequence></div></Window>
    <Sequence from={cf + 36}><Pill text="Narrated, captioned, rendered for you" delay={0} accent="#20c997" /></Sequence></AbsoluteFill>);
}

function Outro({ frames }: { frames: number }) {
  const f = useCurrentFrame(); const rise = interpolate(f, [0, 110], [0.55, 1], { extrapolateRight: "clamp", easing: Easing.bezier(0.16, 1, 0.3, 1) }); const out = interpolate(f, [frames - 40, frames], [1, 0], { extrapolateLeft: "clamp" });
  const logo = interpolate(f, [92, 130], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease });
  return (<AbsoluteFill style={{ opacity: out }}><Glow y={1000} o={0.1} /><Moon rise={rise} /><AbsoluteFill style={{ fontFamily: FONT, justifyContent: "center", alignItems: "center", flexDirection: "column", paddingBottom: 260 }}>
    <div style={{ opacity: 1 - logo * 0.0 }}><Words text="Every claim," size={150} delay={4} /><Words text="traced to its source." size={150} delay={22} gradFrom={1} /></div>
    <div style={{ marginTop: 70, opacity: logo, transform: `translateY(${(1 - logo) * 20}px)`, textAlign: "center" }}><div style={{ fontSize: 64, fontWeight: 700, letterSpacing: 14, color: "#f5f5f7" }}>SCIENTIA AI</div><div style={{ fontSize: 30, color: "#a1a1aa", marginTop: 14, letterSpacing: 2 }}>Research, understood.</div></div></AbsoluteFill></AbsoluteFill>);
}

export const Launch: React.FC<LaunchProps> = ({ scenes, music, duck }) => {
  let at = 0; const total = scenes.reduce((a, s) => a + s.frames, 0);
  const vol = (f: number) => { let v = interpolate(f, [0, 60, total - 90, total], [0, 0.5, 0.5, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }); for (const [a, b] of duck) v *= interpolate(f, [a - 12, a, b, b + 20], [1, 0.16, 0.16, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }); return v; };
  return (<AbsoluteFill style={{ background: "#000" }}><Audio src={staticFile(music)} volume={vol} />{scenes.map((s, i) => { const from = at; at += s.frames;
    return <Sequence key={i} from={from} durationInFrames={s.frames}>{s.type === "intro" ? <Intro frames={s.frames} /> : s.type === "clip" ? <ClipScene sc={s} /> : s.type === "audio" ? <AudioScene sc={s} /> : s.type === "wall" ? <Wall sc={s} /> : s.type === "video" ? <VideoScene sc={s} /> : <Outro frames={s.frames} />}</Sequence>; })}</AbsoluteFill>);
};
