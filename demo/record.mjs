// Scripted, cursor-visible screen recording of the real SCIENTIA AI UI via Chrome DevTools screencast.
// usage: node demo/record.mjs <workdir> <token> <pdf> <pid-file>   -> writes <workdir>/clips/<name>/{frames,index.json}
import { spawn } from "node:child_process"; import fs from "node:fs"; import path from "node:path";
const [WORK, TOKEN, PDF] = process.argv.slice(2); const BASE = "http://localhost:5174"; const W = 1440, H = 900, DSF = 1.5;
const shell = fs.readdirSync(`${process.env.HOME}/scientia-ai/video/node_modules/.remotion/chrome-headless-shell/mac-arm64`)[0];
const bin = `${process.env.HOME}/scientia-ai/video/node_modules/.remotion/chrome-headless-shell/mac-arm64/${shell}/chrome-headless-shell`;
fs.mkdirSync(`${WORK}/clips`, { recursive: true });
const ONLY = new Set((process.env.STAGES || "upload,ask,mindmap,audio,slides,video").split(","));
const ch = spawn(bin, ["--remote-debugging-port=9444", "--no-sandbox", "--hide-scrollbars", "--autoplay-policy=no-user-gesture-required", `--window-size=${W},${H}`, `--user-data-dir=${WORK}/prof`, "about:blank"], { stdio: "ignore" });
const sleep = ms => new Promise(r => setTimeout(r, ms));
let list; for (let i = 0; i < 60; i++) { try { list = await (await fetch("http://127.0.0.1:9444/json/list")).json(); if (list.length) break; } catch {} await sleep(250); }
const ws = new WebSocket(list.find(t => t.type === "page").webSocketDebuggerUrl); await new Promise(r => (ws.onopen = r));
let id = 0; const pend = new Map(); let onFrame = null;
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } else if (m.method === "Page.screencastFrame") { onFrame?.(m.params); send("Page.screencastFrameAck", { sessionId: m.params.sessionId }); } };
const send = (method, params = {}) => new Promise(r => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async (expr) => { const r = await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true }); if (r.result?.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails).slice(0, 300)); return r.result?.result?.value; };
const waitFor = async (expr, ms = 900000) => { const t = Date.now(); while (Date.now() - t < ms) { if (await ev(`!!(${expr})`).catch(() => false)) return true; await sleep(400); } console.log("WAIT TIMEOUT:", expr.slice(0, 70)); return false; };

// ---- recorder with speed markers ------------------------------------------------------------------------------------------------
let cur = null;
async function startClip(name) { const dir = `${WORK}/clips/${name}`; fs.rmSync(dir, { recursive: true, force: true }); fs.mkdirSync(`${dir}/frames`, { recursive: true }); cur = { name, dir, frames: [], speeds: [{ t: Date.now() / 1000, k: 1 }], n: 0 };
  onFrame = p => { const f = `${String(cur.n++).padStart(6, "0")}.jpg`; fs.writeFileSync(`${dir}/frames/${f}`, Buffer.from(p.data, "base64")); cur.frames.push({ f, ts: p.metadata.timestamp }); };
  await send("Page.startScreencast", { format: "jpeg", quality: 88, maxWidth: W * DSF, maxHeight: H * DSF, everyNthFrame: 1 }); await sleep(250); }
const speed = k => cur.speeds.push({ t: Date.now() / 1000, k });
async function endClip() { await sleep(400); await send("Page.stopScreencast"); onFrame = null; fs.writeFileSync(`${cur.dir}/index.json`, JSON.stringify({ frames: cur.frames, speeds: cur.speeds, end: Date.now() / 1000 })); console.log("clip", cur.name, cur.frames.length, "frames"); }

// ---- visible cursor + human-like actions ------------------------------------------------------------------------------------------
const CURSOR = `(()=>{ if(window.__cur) return; const c=document.createElement('div'); c.style.cssText='position:fixed;left:0;top:0;width:30px;height:30px;z-index:2147483647;pointer-events:none;transition:transform .75s cubic-bezier(.22,.8,.2,1);transform:translate(760px,520px);filter:drop-shadow(0 3px 5px rgba(0,0,0,.55))';
 c.innerHTML='<svg width="30" height="30" viewBox="0 0 24 24"><path d="M5 3l14 8-6 1.6L10.4 19 5 3z" fill="#fff" stroke="#111" stroke-width="1.4" stroke-linejoin="round"/></svg>'; document.body.appendChild(c); window.__cur=c;
 window.__move=(x,y)=>{c.style.transform='translate('+x+'px,'+y+'px)'}; window.__ripple=(x,y)=>{const r=document.createElement('div'); r.style.cssText='position:fixed;left:'+(x-6)+'px;top:'+(y-6)+'px;width:12px;height:12px;border-radius:50%;border:3px solid #38bdf8;z-index:2147483646;pointer-events:none;transition:all .55s ease-out;opacity:.95'; document.body.appendChild(r); requestAnimationFrame(()=>{r.style.transform='scale(5)';r.style.opacity='0'}); setTimeout(()=>r.remove(),700)} })()`;
const rectOf = (find) => ev(`(()=>{const el=(${find}); if(!el) return null; el.scrollIntoView({block:'nearest'}); const r=el.getBoundingClientRect(); return {x:r.left+Math.min(r.width/2,60), y:r.top+r.height/2}})()`);
async function pointAndClick(find, { dwell = 750, after = 500 } = {}) { const r = await rectOf(find); if (!r) throw new Error("not found: " + find); await ev(`window.__move(${r.x},${r.y})`); await sleep(dwell); await ev(`window.__ripple(${r.x},${r.y})`); await ev(`(${find}).click()`); await sleep(after); }
const byText = (t, sel = "button") => `[...document.querySelectorAll('${sel}')].find(b=>b.textContent.includes(${JSON.stringify(t)})&&!b.disabled)`;
async function typeText(text, delay = 62) { for (const ch of text) { await send("Input.dispatchKeyEvent", { type: "keyDown", text: ch, key: ch, unmodifiedText: ch }); await send("Input.dispatchKeyEvent", { type: "keyUp", key: ch }); await sleep(delay + Math.random() * 38); } }
const smoothScroll = (y) => ev(`window.scrollTo({top:${y},behavior:'smooth'})`);

// ---- session ------------------------------------------------------------------------------------------------------------------------
await send("Runtime.enable"); await send("Page.enable"); await send("Emulation.setDeviceMetricsOverride", { width: W, height: H, deviceScaleFactor: DSF, mobile: false });
await send("Page.addScriptToEvaluateOnNewDocument", { source: `localStorage.setItem('token', ${JSON.stringify(TOKEN)})` });
await send("Page.navigate", { url: BASE }); await sleep(2500); await ev(CURSOR);
const pdfB64 = fs.readFileSync(PDF).toString("base64"); const pdfName = path.basename(PDF);

const dz = `document.querySelector('div[class*="border-dashed"]')`;
async function dropPdf() {
  const r0 = await rectOf(dz); await ev(`window.__move(${r0.x + 200},${r0.y + 60})`); await sleep(900);
  await ev(`(()=>{const bin=Uint8Array.from(atob(${JSON.stringify(pdfB64)}),c=>c.charCodeAt(0));const f=new File([bin],${JSON.stringify(pdfName)},{type:'application/pdf'});const dt=new DataTransfer();dt.items.add(f);const z=${dz};window.__dt=dt;z.dispatchEvent(new DragEvent('dragover',{dataTransfer:dt,bubbles:true,cancelable:true}))})()`); await sleep(1100);
  await ev(`(()=>{const z=${dz};z.dispatchEvent(new DragEvent('drop',{dataTransfer:window.__dt,bubbles:true,cancelable:true}))})()`); await sleep(1500);
}
const heading = (t) => `[...document.querySelectorAll('h3')].find(h=>h.textContent==='${t}')`;
const uncheckFluent = async () => { const f = `[...document.querySelectorAll('input[type=checkbox]')].find(i=>i.parentElement.textContent.includes('explain in natural language'))`; if (await ev(`!!(${f})&&(${f}).checked`)) await pointAndClick(f, { dwell: 500, after: 400 }); };
const stages = {
  async upload() { await startClip("upload"); await sleep(900);
    await pointAndClick(byText("＋ Upload paper"), { after: 900 }); await dropPdf();
    await pointAndClick(byText("Upload & index"), { after: 300 }); speed(3);
    await waitFor(`document.body.innerText.includes('chunks')`, 120000); speed(1); await sleep(2600); await endClip(); },
  async ask() { await startClip("ask"); await sleep(600);
    await pointAndClick(byText("Studio", "nav button"), { after: 1100 });
    await pointAndClick(`document.querySelector('textarea')`, { after: 300 }); await ev(`document.querySelector('textarea').focus()`); await sleep(200); await typeText("What's the plan of NASA for the Moon?"); await sleep(700);
    await pointAndClick(byText("Ask sources"), { after: 300 }); speed(8);
    await waitFor(`document.querySelector('p.leading-relaxed')`, 300000); speed(1); await sleep(700);
    await ev(`document.querySelector('p.leading-relaxed').scrollIntoView({behavior:'smooth',block:'start'})`); await sleep(5200);
    await ev(`window.scrollTo({top:document.querySelector('p.leading-relaxed').getBoundingClientRect().top+window.scrollY-120,behavior:'smooth'})`); await sleep(1400);
    await pointAndClick(`[...document.querySelectorAll('div[id^="cite-"] button')][0]`, { after: 3200 }); await endClip(); },
  async mindmap() { await startClip("mindmap"); await ev(`window.scrollTo({top:0})`); await sleep(900);
    await pointAndClick(byText("Mind map", "button"), { after: 200 });
    await waitFor(`document.querySelector('[data-node]')`, 120000); await sleep(900);
    await ev(`document.querySelector('[data-node]').closest('.rounded-2xl').scrollIntoView({behavior:'smooth',block:'center'})`); await sleep(2800);
    await pointAndClick(byText("Fit"), { dwell: 600, after: 1400 });
    await pointAndClick(`[...document.querySelectorAll('[data-node]')].find(n=>n.textContent.includes('Artemis Base Camp'))`, { after: 3200 }); await endClip(); },
  async audio() { await startClip("audio"); await ev(`window.scrollTo({top:0,behavior:'smooth'})`); await sleep(1000); await uncheckFluent();
    await pointAndClick(byText("Audio overview", "button"), { after: 300 }); speed(14);
    await waitFor(`document.body.innerText.includes('Host A')`, 1200000); speed(1); await sleep(600);
    await ev(`document.querySelector('audio').scrollIntoView({behavior:'smooth',block:'center'})`); await sleep(1500);
    await ev(`(()=>{const a=document.querySelector('audio'); a.muted=true; a.play().catch(()=>{})})()`); await sleep(7000); await endClip(); },
  async slides() { await startClip("slides"); await ev(`window.scrollTo({top:0,behavior:'smooth'})`); await sleep(900);
    await pointAndClick(byText("Slides", "button"), { after: 300 }); speed(6);
    await waitFor(`document.body.innerText.includes('Download PowerPoint')`, 600000); speed(1); await sleep(900);
    await ev(`document.querySelector('img[alt^="Slide"]').scrollIntoView({behavior:'smooth',block:'center'})`); await sleep(1800);
    for (let i = 0; i < 6; i++) { await pointAndClick(byText("Next"), { dwell: 420, after: 1250 }); }
    await pointAndClick(byText("Download PowerPoint", "a"), { dwell: 500, after: 600 }); await endClip(); },
  async video() { await startClip("video"); await ev(`window.scrollTo({top:0,behavior:'smooth'})`); await sleep(900); await uncheckFluent();
    await pointAndClick(byText("Video overview", "button"), { after: 300 }); speed(24);
    await waitFor(`document.body.innerText.includes('Rendered with')`, 1800000); speed(1); await sleep(600);
    await ev(`document.querySelector('video').scrollIntoView({behavior:'smooth',block:'center'})`); await sleep(1800);
    await ev(`(()=>{const v=document.querySelector('video'); v.muted=true; v.play().catch(()=>{})})()`); await sleep(7000); await endClip(); },
};
// when resuming later stages, silently re-add the paper as a source (the file is already in the library -> "already in library")
if (!ONLY.has("upload")) { await pointAndClick(byText("＋ Upload paper"), { after: 600 }); await dropPdf(); await pointAndClick(byText("Upload & index"), { after: 300 }); await waitFor(`document.body.innerText.includes('chunks')`, 120000); await sleep(800); await pointAndClick(byText("Studio", "nav button"), { after: 800 }); }
for (const name of Object.keys(stages)) if (ONLY.has(name)) { console.log("stage", name); await stages[name](); }
console.log("RECORDING DONE"); ch.kill(); process.exit(0);
