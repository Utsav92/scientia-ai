// usage: node render.mjs <props.json> --publicDir DIR [--stills DIR] [--video OUT.mp4] [--scale 0.6667]
import { bundle } from "@remotion/bundler"; import { renderMedia, renderStill, selectComposition } from "@remotion/renderer";
import fs from "node:fs"; import path from "node:path"; import { fileURLToPath } from "node:url";
const here = path.dirname(fileURLToPath(import.meta.url));
const a = process.argv.slice(2); const props = JSON.parse(fs.readFileSync(a[0], "utf8"));
const opt = (k, d) => { const i = a.indexOf("--" + k); return i >= 0 ? a[i + 1] : d; };
const publicDir = opt("publicDir"), stills = opt("stills"), video = opt("video"), scale = parseFloat(opt("scale", "1"));
const log = (m) => console.log(JSON.stringify(m));
const serveUrl = await bundle({ entryPoint: path.join(here, "src/index.ts"), publicDir, onProgress: () => {} });
const comp = await selectComposition({ serveUrl, id: "Deck", inputProps: props }); log({ stage: "bundled", frames: comp.durationInFrames });
if (stills) {
  fs.mkdirSync(stills, { recursive: true }); let start = 0;
  for (let i = 0; i < props.slides.length; i++) { const s = props.slides[i]; const frame = start + Math.min(Math.max(1, s.frames - 12), 80);
    await renderStill({ composition: comp, serveUrl, output: path.join(stills, `slide_${String(i + 1).padStart(2, "0")}.png`), frame, inputProps: props }); start += s.frames; log({ stage: "still", i: i + 1, of: props.slides.length }); }
}
if (video) {
  let last = -1;
  await renderMedia({ composition: comp, serveUrl, codec: "h264", outputLocation: video, inputProps: props, scale, crf: 23, onProgress: ({ progress }) => { const p = Math.floor(progress * 20); if (p !== last) { last = p; log({ stage: "video", progress: progress }); } } });
}
log({ stage: "done" });
