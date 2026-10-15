# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Project

twizzers (originally scaffolded under the name "Tweezers"; see `SCAFFOLD.md` for the original write-up) lets people express gratitude/feelings to a loved one: sign up, write or AI-generate a poem, pick an animated template and music, and get a shareable creation with a public link.

## Layout

- `backend/` - FastAPI + SQLAlchemy + Postgres API. `app/main.py` registers routers in `app/routers/` (auth, poems, templates, music, creations, credits). `app/ai.py` calls the Anthropic API for poems (falls back to demo text without a key). `app/cashfree_client.py` handles Cashfree orders, order-status checks and webhook signature verification.
- `frontend-demo/index.html` - plain HTML/JS page exercising the full create flow against the API.
- `web-checkout/credits.html` - standalone credit-purchase page, hosted outside the app on purpose (avoids Google Play billing).
- `mobile/` - React Native app (Expo, TypeScript), currently the blank template. App scheme is `tweezers`. Check the versioned Expo docs before writing Expo code (see `mobile/AGENTS.md`); add packages with `npx expo install`. Typecheck with `npx tsc --noEmit`.
- `docker-compose.yml` - Postgres + backend.
- `docs/PROJECT_DISCUSSION.md` - product decisions, roadmap, stack, hosting plan and future ideas (e.g. AI image generation). Read it for context and keep it updated when decisions change.

## Commands

- Run everything: `cp backend/.env.example backend/.env && docker compose up --build`, then `docker compose exec backend python seed_data.py`. API docs at `http://localhost:8000/docs`.
- Run without Docker: in `backend/`, `pip install -r requirements.txt`, set `DATABASE_URL`, then `uvicorn app.main:app --reload` and `python seed_data.py`.
- There are no tests or lint config yet.

## Notes

- `PAYMENTS_ENABLED` (default `false`) gates the whole credits system; while off, poem generation is free and checkout returns 503.
- Stubbed: video rendering (creations are marked ready with a placeholder URL), auth (no OTP/password), placeholder template/music URLs.
- Payments use Cashfree (originally Razorpay in the scaffold). Env vars: `CASHFREE_CLIENT_ID`, `CASHFREE_CLIENT_SECRET`, `CASHFREE_ENV` (`sandbox`|`production`), `CASHFREE_NOTIFY_URL`. The Cashfree client was written without access to Cashfree's docs and has not been run against the sandbox.
- Decided stack: React Native (Expo) for the app, Firebase Auth (phone OTP) for login, Neon (managed Postgres) for the production database.
- Never commit `backend/.env` or real API keys.
- Develop on the `claude/epic-gates-5rqbqc` branch.
