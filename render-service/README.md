# render-service

Remotion service that renders a poem into a 1080x1920 H.264 video (plus a JPEG thumbnail).

```bash
cd render-service
npm install
RENDER_SECRET=change-me npm start          # listens on :4000, output in ./out
```

Env: `RENDER_SECRET` (required, shared with the backend), `PORT` (4000), `OUTPUT_DIR` (`./out`), `PUBLIC_BASE_URL` (`http://localhost:PORT`), `BROWSER_EXECUTABLE` (optional path to a Chromium/headless shell; otherwise Remotion downloads its own). The host needs Chromium's system libraries.

API: `POST /render` (header `x-render-secret`) with `{job_id, poem, recipient?, mood_tags?, music_url?, callback_url}` returns 202. Jobs run one at a time; the result (`{job_id, status: ready|failed, video_url, thumbnail_url}`) is POSTed to `callback_url` with the same secret header. If rendering fails with a music URL, it retries once without music. Files are served at `/files/<job_id>.mp4` and `.jpg`.

Preview the composition: `npm run studio`.

Not done yet: upload to Cloudflare R2 (files are only on local disk), a Dockerfile for deployment, real Lottie/Rive templates. Check Remotion's licence terms for commercial use before launch.
