# Tweezers — Phase 1 Scaffold

This is a working backend + demo frontend for the Phase 1 MVP described in
the planning conversation: users sign up, write or AI-generate a poem,
pick an animated template + music, and get a shareable "creation" with a
public link (ready to post to Instagram/WhatsApp).

**This has been tested end-to-end** (signup → generate poem → select
variant → pick template/music → create → fetch via public share link) —
see `backend/` below for how to run it yourself.

## What's included

```
tweezers/
├── backend/              FastAPI + SQLAlchemy + Postgres API
│   ├── app/
│   │   ├── main.py           App entrypoint, router registration
│   │   ├── models.py         SQLAlchemy models (matches the data model)
│   │   ├── schemas.py        Pydantic request/response schemas
│   │   ├── ai.py             Claude API call for poem generation
│   │   ├── database.py       DB session/engine setup
│   │   └── routers/
│   │       ├── auth.py       Simplified signup (swap for Firebase/Clerk)
│   │       ├── poems.py      Write / generate / select-variant
│   │       ├── templates.py  List animation templates
│   │       ├── music.py      List music tracks
│   │       └── creations.py  Assemble poem+template+music, share links
│   ├── seed_data.py      Populates starter templates + music tracks
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend-demo/
│   └── index.html         Plain HTML/JS page that exercises the full
│                           create flow against the API — use this to
│                           test/demo before building the real React
│                           Native app
├── web-checkout/
│   └── credits.html       STANDALONE credits purchase page — hosted on
│                           its own domain, OUTSIDE the app, so buying
│                           credits here is not an in-app purchase and
│                           does not go through Google Play Billing.
│                           Opens Razorpay checkout, confirms payment,
│                           redirects back into the app via a deep link.
├── docker-compose.yml     Postgres + backend, one command to run locally
└── README.md              This file
```

## Payments are OFF by default — everything is free right now

Story generation costs nothing until you decide to turn on payments.
This is controlled by one flag, `PAYMENTS_ENABLED` (default `false`):

- **Off (default):** `poems/generate` never checks or deducts credits —
  works even for a brand-new user with a 0 balance. The `/credits/checkout/*`
  endpoints return `503 Payments are not enabled yet`, and the web checkout
  page (`web-checkout/credits.html`) shows an "everything's free for now"
  banner instead of letting anyone pay.
- **On:** set `PAYMENTS_ENABLED=true` in your environment (see
  `backend/.env.example` / `docker-compose.yml`) and redeploy — no code
  changes needed. Generation immediately starts enforcing the credit
  balance and checkout opens back up.

Nothing about the credits system was removed — wallets, packs, Razorpay
order creation and signature verification, the webhook, all of it still
runs underneath. Flipping the flag back on later just re-activates the
checks; existing user data isn't touched.

## Credits system (Google Play billing avoidance)

Story generation is priced in **credits** (1 credit = Rs 1 by convention;
one generation costs `COST_PER_STORY_CREDITS`, default 5 — so Rs 5 per
story, adjustable via env var to fit your Rs 1–10 target range).

**Credits can only be bought outside the app**, via `web-checkout/credits.html`,
which you host on your own domain (e.g. `pay.yourtweezers.com`). This is
deliberate: since the purchase happens in a browser, not inside the
Android app, it is not an "in-app purchase" under Google Play policy, so
Google does not take a commission — you keep the full amount minus
Razorpay's own gateway fee (~2%).

### How the flow works end-to-end

1. Inside the app, when a user is low on credits, show a "Buy Credits"
   button that opens `web-checkout/credits.html?user_id={id}&api={backend_url}`
   in the device's browser (`Intent`/`CustomTabs` on Android — NOT a
   WebView embedded in the app, since some interpretations of Play policy
   still treat an in-app WebView checkout as effectively "in-app").
2. The page loads available credit packs (`GET /credits/packs`) and shows
   the user's current balance (`GET /credits/balance/{user_id}`).
3. User picks a pack → page calls `POST /credits/checkout/create-order`,
   which creates a Razorpay Order server-side and returns the order ID.
4. Razorpay's checkout.js opens (hosted payment UI, handles cards/UPI/etc).
5. On success, the page calls `POST /credits/checkout/verify` with the
   payment details — the backend verifies the HMAC signature Razorpay
   provides and credits the user's wallet (idempotently).
6. The page redirects back into the app via a custom URL scheme
   (`tweezers://credits-success?...` — register this scheme in your
   Android/iOS app). A Razorpay webhook (`POST /credits/webhook`) is the
   backup source of truth in case the browser closes right after payment,
   before the redirect fires.
7. Back in the app, `poems/generate` checks and deducts credits
   automatically — returns `402 Payment Required` with a clear message if
   the balance is too low.

### Setting this up for real

- Get Razorpay API keys at https://dashboard.razorpay.com/app/keys and set
  `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` in `backend/.env`
- Configure a webhook in the Razorpay dashboard pointing at
  `https://yourdomain.com/credits/webhook`, subscribed to the
  `payment.captured` event, and set `RAZORPAY_WEBHOOK_SECRET` to match
- Host `web-checkout/credits.html` on your own domain (any static host —
  Cloudflare Pages, Vercel, S3, etc. all work since it's a single file)
- Register `tweezers://credits-success` (or your own scheme) as a deep
  link in your Android app's manifest / iOS Info.plist so the redirect
  in step 6 actually opens your app

## Running it locally

**Option A — Docker (recommended, no local Python/Postgres needed):**

```bash
cd tweezers
cp backend/.env.example backend/.env   # then add your ANTHROPIC_API_KEY
docker compose up --build
```

API will be live at `http://localhost:8000` (interactive docs at
`http://localhost:8000/docs`). Then seed starter templates/music:

```bash
docker compose exec backend python seed_data.py
```

**Option B — Local Python + your own Postgres:**

```bash
cd tweezers/backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL="postgresql://user:pass@localhost:5432/tweezers"
export ANTHROPIC_API_KEY="sk-ant-..."
uvicorn app.main:app --reload
python seed_data.py   # in a second terminal
```

**Try the demo frontend:** just open `frontend-demo/index.html` in a
browser (or `python -m http.server` inside that folder). It walks through
signup → AI poem generation → template/music picking → creation →
share link, calling your running backend.

## Without an Anthropic API key

`app/ai.py` falls back to placeholder poem text if `ANTHROPIC_API_KEY`
isn't set, so the whole flow (including the demo frontend) is fully
testable without a key. Add a real key to get actual generated poems.

## What's intentionally stubbed (see roadmap)

- **Video rendering**: `creations.py` marks a creation `ready` immediately
  with a placeholder URL instead of actually rendering a video. Next step:
  stand up a Remotion-based render service (Node) that takes
  `poem + template + music` and outputs an MP4, then have this endpoint
  enqueue a job there instead of faking it. Store output in Cloudflare R2
  (see cost discussion below) and update `rendered_video_url` when done.
- **Auth**: `auth.py` is a bare signup with no OTP/password verification.
  Swap for Firebase Auth or Clerk before any real users touch this.
- **Templates/music files**: seed data uses placeholder CDN URLs. Replace
  with real Lottie/Rive files and licensed audio (Epidemic Sound/Artlist).
- **Physical card, prepaid balance**: Phase 2/3 — not part of this
  scaffold. The `orders` table from the data model isn't built yet;
  add it when you're ready to build that flow.

## Infra notes

- Use **Cloudflare R2** for storing rendered videos/thumbnails — zero
  egress fees matter a lot here since your growth loop is people sharing
  videos widely (lots of outbound bandwidth). Cloudflare CDN in front for
  fast global delivery, including good performance in India.
- `DATABASE_URL` env var controls the DB connection everywhere — swap to
  any managed Postgres (RDS, Supabase, Neon, etc.) for production.

## Suggested next steps

1. Wire up a real render pipeline (Remotion) — this is the biggest gap
   between "API works" and "app actually produces the animated video."
2. Replace the demo frontend with the real React Native app, hitting the
   same API.
3. Swap auth stub for Firebase Auth/Clerk with real OTP verification.
4. Add the `orders` table + endpoints when starting Phase 2 (physical
   card).
