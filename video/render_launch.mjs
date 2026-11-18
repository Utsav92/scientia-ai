// usage: node render_launch.mjs <props.json> --publicDir DIR (--still FRAME OUT.png | --video OUT.mp4 [--scale 1])
import { bundle } from "@remotion/bundler"; import { renderMedia, renderStill, selectComposition } from "@remotion/renderer";
import fs from "node:fs"; import path from "node:path"; import { fileURLToPath } from "node:url";
const here = path.dirname(fileURLToPath(import.meta.url)); const a = process.argv.slice(2); const props = JSON.parse(fs.readFileSync(a[0], "utf8"));
const opt = (k) => { const i = a.indexOf("--" + k); return i >= 0 ? a.slice(i + 1) : null; };
const publicDir = opt("publicDir")[0]; const still = opt("still"); const video = opt("video");
const serveUrl = await bundle({ entryPoint: path.join(here, "src/index.ts"), publicDir, onProgress: () => {} });
const comp = await selectComposition({ serveUrl, id: "Launch", inputProps: props }); console.log(JSON.stringify({ frames: comp.durationInFrames }));
if (still) { await renderStill({ composition: comp, serveUrl, output: still[1], frame: parseInt(still[0]), inputProps: props }); console.log("still ok"); }
if (video) { let last = -1; await renderMedia({ composition: comp, serveUrl, codec: "h264", outputLocation: video[0], inputProps: props, crf: 16, audioBitrate: "256k", onProgress: ({ progress }) => { const p = Math.floor(progress * 50); if (p !== last) { last = p; console.log(JSON.stringify({ progress })); } } }); console.log("video ok"); }
