# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Project

twizzers (originally scaffolded under the name "Tweezers"; see `SCAFFOLD.md` for the original write-up) lets people express gratitude/feelings to a loved one: sign up, write or AI-generate a poem, pick an animated template and music, and get a shareable creation with a public link.

## Layout

- `backend/` - FastAPI + SQLAlchemy + Postgres API. `app/main.py` registers routers in `app/routers/` (auth, poems, templates, music, creations, credits). `app/ai.py` calls the Anthropic API for poems (falls back to demo text without a key). `app/firebase_auth.py` verifies Firebase ID tokens (`POST /auth/firebase`, `GET /auth/me`, `get_current_user` dependency). `alembic/` holds DB migrations. `app/cashfree_client.py` handles Cashfree orders, order-status checks and webhook signature verification.
- `frontend-demo/index.html` - plain HTML/JS page exercising the full create flow against the API.
- `web-checkout/credits.html` - standalone credit-purchase page, hosted outside the app on purpose (avoids Google Play billing).
- `mobile/` - React Native app (Expo, TypeScript), currently the blank template. App scheme is `tweezers`. Check the versioned Expo docs before writing Expo code (see `mobile/AGENTS.md`); add packages with `npx expo install`. Typecheck with `npx tsc --noEmit`.
- `docker-compose.yml` - Postgres + backend.
- `render-service/` - Remotion (Node) service that turns a poem into a 9:16 MP4. `src/remotion/` is the composition (`PoemVideo`). Remotion docs were not reachable from the sandbox; render tested with Chromium at `/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell`.
- `docs/ARCHITECTURE.md` - which service is used for each task (AI and web services), system diagram, working flows, env vars. Keep it updated when a service or flow changes.
- `docs/PROJECT_DISCUSSION.md` - product decisions, roadmap, stack, hosting plan and future ideas (e.g. AI image generation). Read it for context and keep it updated when decisions change.

## Commands

- Run everything: `cp backend/.env.example backend/.env && docker compose up --build` (set `AUTH_DEV_BYPASS=true` in your shell or `.env` to use frontend-demo), then `docker compose exec backend python seed_data.py`. API docs at `http://localhost:8000/docs`.
- Run without Docker: in `backend/`, `pip install -r requirements.txt`, set `DATABASE_URL`, then `uvicorn app.main:app --reload` and `python seed_data.py`.
- Migrations: the schema is managed by Alembic (Docker runs `alembic upgrade head` on start). After changing `models.py`, in `backend/` run `alembic revision --autogenerate -m "msg"`, review the file, then `alembic upgrade head`.
- Render service: `cd render-service && npm install && RENDER_SECRET=... npm start`; see its README.
- There are no automated tests or lint config yet.

## Notes

- `PAYMENTS_ENABLED` (default `false`) gates the whole credits system; while off, poem generation is free and checkout returns 503.
- Video rendering: with `RENDER_SERVICE_URL` set the backend sends jobs to `render-service/` and gets the result by callback; with it empty, creations are marked ready with a placeholder URL. Stubbed: R2 upload, placeholder template/music URLs. Auth: `POST /auth/firebase` is the real login. All user-owned routes (poems, creations, credits balance/checkout) require `Authorization: Bearer <Firebase ID token>` via `get_current_user` and check ownership; public routes are templates, music, credit packs, `/creations/share/{slug}` and the signed payment webhook. `FIREBASE_PROJECT_ID` is required for token verification. For local demos only, `AUTH_DEV_BYPASS=true` accepts `Bearer dev:<user_id>` and enables `POST /auth/signup` (frontend-demo needs it); never enable it in production.
- Payments use Cashfree (originally Razorpay in the scaffold). Env vars: `CASHFREE_CLIENT_ID`, `CASHFREE_CLIENT_SECRET`, `CASHFREE_ENV` (`sandbox`|`production`), `CASHFREE_NOTIFY_URL`. The Cashfree client was written without access to Cashfree's docs and has not been run against the sandbox (only against a mocked Cashfree).
- Decided stack: React Native (Expo) for the app, Firebase Auth (phone OTP) for login, Neon (managed Postgres) for the production database.
- Never commit `backend/.env` or real API keys.
- Develop on the `claude/epic-gates-5rqbqc` branch.
