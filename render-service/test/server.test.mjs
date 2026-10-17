// Run with: npm test   (no browser needed; rendering itself is covered by the smoke test)
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const PORT = 4300 + Math.floor(Math.random() * 500);
const SECRET = "test-secret";
const dir = fs.mkdtempSync(path.join(os.tmpdir(), "render-test-"));
const base = `http://localhost:${PORT}`;
let server;

before(async () => {
  server = spawn("node", ["src/server.mjs"], {
    env: { ...process.env, RENDER_SECRET: SECRET, PORT: String(PORT), OUTPUT_DIR: dir, R2_ENDPOINT: "", R2_BUCKET: "" },
    stdio: "ignore",
  });
  for (let i = 0; i < 50; i++) {
    try {
      if ((await fetch(`${base}/health`)).ok) return;
    } catch {}
    await new Promise((r) => setTimeout(r, 200));
  }
  throw new Error("server did not start");
});

after(() => {
  server?.kill();
  fs.rmSync(dir, { recursive: true, force: true });
});

const post = (body, secret = SECRET) =>
  fetch(`${base}/render`, { method: "POST", headers: { "x-render-secret": secret, "content-type": "application/json" }, body: JSON.stringify(body) });

const goodJob = { job_id: "job-1", poem: "one\ntwo", callback_url: "http://localhost:9/cb" };

test("health", async () => {
  assert.equal((await fetch(`${base}/health`)).status, 200);
});

test("render needs the shared secret", async () => {
  assert.equal((await post(goodJob, "wrong")).status, 401);
  assert.equal((await fetch(`${base}/render`, { method: "POST", body: "{}" })).status, 401);
});

test("render rejects bad jobs", async () => {
  for (const bad of [
    { ...goodJob, job_id: "../etc/passwd" },
    { ...goodJob, poem: "" },
    { ...goodJob, poem: "x".repeat(6000) },
    { ...goodJob, callback_url: "ftp://nope" },
    { ...goodJob, music_url: "file:///etc/passwd" },
    { ...goodJob, template_category: "Bad Category!" },
  ]) {
    assert.equal((await post(bad)).status, 400, JSON.stringify(bad).slice(0, 80));
  }
});

test("files: only safe names are served", async () => {
  assert.equal((await fetch(`${base}/files/..%2Fsecret.mp4`)).status, 404);
  assert.equal((await fetch(`${base}/files/missing.mp4`)).status, 404);
  fs.writeFileSync(path.join(dir, "present.mp4"), "video-bytes");
  const ok = await fetch(`${base}/files/present.mp4`);
  assert.equal(ok.status, 200);
  assert.equal(ok.headers.get("content-type"), "video/mp4");
});

test("delete removes a render's files and needs the secret", async () => {
  fs.writeFileSync(path.join(dir, "gone.mp4"), "x");
  fs.writeFileSync(path.join(dir, "gone.jpg"), "x");
  assert.equal((await fetch(`${base}/files/gone`, { method: "DELETE" })).status, 401);
  assert.equal((await fetch(`${base}/files/bad%20id`, { method: "DELETE", headers: { "x-render-secret": SECRET } })).status, 400);
  const res = await fetch(`${base}/files/gone`, { method: "DELETE", headers: { "x-render-secret": SECRET } });
  assert.equal(res.status, 200);
  assert.equal(fs.existsSync(path.join(dir, "gone.mp4")), false);
  assert.equal(fs.existsSync(path.join(dir, "gone.jpg")), false);
  // deleting something that is not there is fine
  assert.equal((await fetch(`${base}/files/never-existed`, { method: "DELETE", headers: { "x-render-secret": SECRET } })).status, 200);
});
