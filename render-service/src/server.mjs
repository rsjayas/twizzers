// HTTP wrapper around the Remotion renderer.
//
//   POST /render   (header x-render-secret)  enqueue a job, returns 202
//   GET  /files/:name                         serve rendered mp4/jpg
//   DELETE /files/:id (header x-render-secret) delete a render's files (local and R2)
//   GET  /health
//
// Jobs run one at a time (rendering is CPU heavy). When a job finishes (or
// fails) the service POSTs the result to the job's callback_url, signed with
// the same shared secret.
//
// Env: RENDER_SECRET (required), PORT (4000), OUTPUT_DIR (./out),
//      PUBLIC_BASE_URL (http://localhost:PORT), BROWSER_EXECUTABLE (optional),
//      R2_* (see storage.mjs) to upload results to Cloudflare R2.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import crypto from "node:crypto";
import { bundle } from "@remotion/bundler";
import { renderMedia, renderStill, selectComposition } from "@remotion/renderer";
import { r2Enabled, uploadFile, deleteObjects } from "./storage.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT || 4000);
const SECRET = process.env.RENDER_SECRET || "";
const OUTPUT_DIR = path.resolve(process.env.OUTPUT_DIR || path.join(here, "..", "out"));
const PUBLIC_BASE_URL = (process.env.PUBLIC_BASE_URL || `http://localhost:${PORT}`).replace(/\/$/, "");
const BROWSER_EXECUTABLE = process.env.BROWSER_EXECUTABLE || undefined;
const MAX_BODY = 200_000;
// Output size as a fraction of 1080x1920. 0.6667 gives 720x1280 (fine for Stories and WhatsApp status,
// about 2x faster); 1 gives full HD.
const RENDER_SCALE = Number(process.env.RENDER_SCALE || 2 / 3);

if (!SECRET) {
  console.error("RENDER_SECRET is required");
  process.exit(1);
}
fs.mkdirSync(OUTPUT_DIR, { recursive: true });

let serveUrlPromise = null;
const getServeUrl = () => {
  serveUrlPromise ??= bundle({ entryPoint: path.join(here, "remotion", "index.jsx") });
  return serveUrlPromise;
};

const safeEqual = (a, b) => {
  const x = Buffer.from(String(a));
  const y = Buffer.from(String(b));
  return x.length === y.length && crypto.timingSafeEqual(x, y);
};

const JOB_ID = /^[A-Za-z0-9_-]{1,64}$/;

function validateJob(body) {
  if (!body || typeof body !== "object") return "body must be an object";
  if (!JOB_ID.test(body.job_id || "")) return "job_id missing or invalid";
  if (typeof body.poem !== "string" || !body.poem.trim()) return "poem is required";
  if (body.poem.length > 5000) return "poem too long";
  if (typeof body.callback_url !== "string" || !/^https?:\/\//.test(body.callback_url)) {
    return "callback_url must be an http(s) URL";
  }
  if (body.music_url != null && !/^https?:\/\//.test(body.music_url)) return "music_url must be an http(s) URL";
  if (body.template_category != null && !/^[a-z0-9_-]{1,40}$/.test(body.template_category)) return "template_category invalid";
  return null;
}

async function renderJob(job) {
  const serveUrl = await getServeUrl();
  const inputProps = {
    poem: job.poem,
    recipient: job.recipient || "",
    moodTags: Array.isArray(job.mood_tags) ? job.mood_tags : [],
    musicUrl: job.music_url || null,
    templateCategory: job.template_category || null,
  };
  const common = { serveUrl, inputProps, browserExecutable: BROWSER_EXECUTABLE, chromiumOptions: { gl: "swangle" } };
  const composition = await selectComposition({ ...common, id: "PoemVideo" });

  const videoFile = `${job.job_id}.mp4`;
  const thumbFile = `${job.job_id}.jpg`;
  await renderMedia({
    ...common,
    composition,
    codec: "h264",
    scale: RENDER_SCALE,
    outputLocation: path.join(OUTPUT_DIR, videoFile),
  });
  // Thumbnail: a frame once a couple of lines are visible.
  await renderStill({
    ...common,
    composition,
    frame: Math.min(composition.durationInFrames - 1, Math.round(composition.fps * 5)),
    imageFormat: "jpeg",
    scale: RENDER_SCALE,
    output: path.join(OUTPUT_DIR, thumbFile),
  });
  if (r2Enabled) {
    const videoPath = path.join(OUTPUT_DIR, videoFile);
    const thumbPath = path.join(OUTPUT_DIR, thumbFile);
    const video_url = await uploadFile(videoPath, `renders/${videoFile}`, "video/mp4");
    const thumbnail_url = await uploadFile(thumbPath, `renders/${thumbFile}`, "image/jpeg");
    // Uploaded: the local copies are no longer needed.
    fs.rmSync(videoPath, { force: true });
    fs.rmSync(thumbPath, { force: true });
    return { video_url, thumbnail_url };
  }
  return { video_url: `${PUBLIC_BASE_URL}/files/${videoFile}`, thumbnail_url: `${PUBLIC_BASE_URL}/files/${thumbFile}` };
}

async function sendCallback(job, payload) {
  try {
    const res = await fetch(job.callback_url, {
      method: "POST",
      headers: { "content-type": "application/json", "x-render-secret": SECRET },
      body: JSON.stringify({ job_id: job.job_id, ...payload }),
    });
    if (!res.ok) console.error(`callback for ${job.job_id} returned ${res.status}`);
  } catch (e) {
    console.error(`callback for ${job.job_id} failed:`, e.message);
  }
}

// --- single-worker queue ---
const queue = [];
let running = false;
async function pump() {
  if (running) return;
  running = true;
  while (queue.length) {
    const job = queue.shift();
    try {
      console.log(`render ${job.job_id} started`);
      let result;
      try {
        result = await renderJob(job);
      } catch (e) {
        // A dead/unreachable music URL shouldn't cost the user their video:
        // retry once without music.
        if (!job.music_url) throw e;
        console.error(`render ${job.job_id} failed with music (${e.message}); retrying without music`);
        result = await renderJob({ ...job, music_url: null });
      }
      console.log(`render ${job.job_id} done`);
      await sendCallback(job, { status: "ready", ...result });
    } catch (e) {
      console.error(`render ${job.job_id} failed:`, e);
      await sendCallback(job, { status: "failed", error: String(e.message || e).slice(0, 500) });
    }
  }
  running = false;
}

const readJson = (req) =>
  new Promise((resolve, reject) => {
    let size = 0;
    const chunks = [];
    req.on("data", (c) => {
      size += c.length;
      if (size > MAX_BODY) {
        reject(new Error("body too large"));
        req.destroy();
      } else chunks.push(c);
    });
    req.on("end", () => {
      try {
        resolve(JSON.parse(Buffer.concat(chunks).toString() || "{}"));
      } catch {
        reject(new Error("invalid JSON"));
      }
    });
    req.on("error", reject);
  });

const send = (res, status, obj) => {
  res.writeHead(status, { "content-type": "application/json" });
  res.end(JSON.stringify(obj));
};

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, "http://x");
    if (req.method === "GET" && url.pathname === "/health") {
      return send(res, 200, { status: "ok", queued: queue.length, running });
    }
    if (req.method === "GET" && url.pathname.startsWith("/files/")) {
      const name = url.pathname.slice("/files/".length);
      if (!/^[A-Za-z0-9_-]{1,64}\.(mp4|jpg)$/.test(name)) return send(res, 404, { error: "not found" });
      const file = path.join(OUTPUT_DIR, name);
      if (!fs.existsSync(file)) return send(res, 404, { error: "not found" });
      res.writeHead(200, { "content-type": name.endsWith(".mp4") ? "video/mp4" : "image/jpeg" });
      return fs.createReadStream(file).pipe(res);
    }
    if (req.method === "DELETE" && url.pathname.startsWith("/files/")) {
      if (!safeEqual(req.headers["x-render-secret"] || "", SECRET)) return send(res, 401, { error: "unauthorized" });
      const id = url.pathname.slice("/files/".length);
      if (!JOB_ID.test(id)) return send(res, 400, { error: "invalid id" });
      for (const ext of ["mp4", "jpg"]) fs.rmSync(path.join(OUTPUT_DIR, `${id}.${ext}`), { force: true });
      try {
        await deleteObjects([`renders/${id}.mp4`, `renders/${id}.jpg`]);
      } catch (e) {
        console.error(`delete of ${id} from storage failed:`, e.message);
        return send(res, 502, { error: "storage delete failed" });
      }
      return send(res, 200, { deleted: id });
    }
    if (req.method === "POST" && url.pathname === "/render") {
      if (!safeEqual(req.headers["x-render-secret"] || "", SECRET)) return send(res, 401, { error: "unauthorized" });
      const job = await readJson(req);
      const err = validateJob(job);
      if (err) return send(res, 400, { error: err });
      queue.push(job);
      pump();
      return send(res, 202, { accepted: true, job_id: job.job_id, queued: queue.length });
    }
    send(res, 404, { error: "not found" });
  } catch (e) {
    send(res, 400, { error: String(e.message || e) });
  }
});

server.listen(PORT, () => {
  console.log(`render-service listening on :${PORT}, output ${OUTPUT_DIR}`);
  getServeUrl().then(() => console.log("bundle ready")).catch((e) => console.error("bundle failed", e));
});
