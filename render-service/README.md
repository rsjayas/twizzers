# render-service

Remotion service that renders a poem into a 1080x1920 H.264 video (plus a JPEG thumbnail).

```bash
cd render-service
npm install
RENDER_SECRET=change-me npm start          # listens on :4000, output in ./out
```

Env: `RENDER_SECRET` (required, shared with the backend), `PORT` (4000), `OUTPUT_DIR` (`./out`), `PUBLIC_BASE_URL` (`http://localhost:PORT`), `BROWSER_EXECUTABLE` (optional path to a Chromium/headless shell; otherwise Remotion downloads its own). The host needs Chromium's system libraries.

API: `POST /render` (header `x-render-secret`) with `{job_id, poem, recipient?, mood_tags?, music_url?, callback_url}` returns 202. Jobs run one at a time; the result (`{job_id, status: ready|failed, video_url, thumbnail_url}`) is POSTed to `callback_url` with the same secret header. If rendering fails with a music URL, it retries once without music. Without R2, files are served at `/files/<job_id>.mp4` and `.jpg`.

Looks: the four seeded templates have their own animation (`sunset_walk`, `cherry_blossom`, `starry_night`, `cozy_rain`, chosen from the job's `template_category`); anything else gets a soft mood gradient with falling petals. Output is 720x1280 by default (`RENDER_SCALE`, a fraction of 1080x1920; set 1 for full HD, which takes about twice as long). `DELETE /files/<job_id>` (secret header) removes a render's files locally and from R2.

Tests: `npm test` (API validation, secrets, safe file names, delete; no browser needed).

Preview the composition: `npm run studio`.

Storage: set `R2_ENDPOINT` (`https://<account-id>.r2.cloudflarestorage.com`), `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET` and `R2_PUBLIC_BASE_URL` (the bucket's public/CDN domain) to upload finished files to Cloudflare R2; the callback then carries the CDN URLs and the local copies are deleted. Without them, files stay in `OUTPUT_DIR` and are served by this process (local dev only).

Docker: `docker build -t tweezers-render render-service` (installs Chromium libraries, Noto fonts for Hindi and other Indian scripts, and Remotion's headless Chrome).

Not done yet: real Lottie/Rive templates (the four looks above are drawn in code). The Dockerfile has not been built (no Docker daemon in the dev sandbox); the R2 upload was tested only against a fake S3 endpoint, not real R2. Check Remotion's licence terms for commercial use before launch.
