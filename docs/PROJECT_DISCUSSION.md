# Tweezers — Project Discussion Log

A running record of the product idea, decisions, and answers from the planning conversation. Update this file as decisions change. For the service-by-task table, system diagram and working flows see `ARCHITECTURE.md`.

_Last updated: 13 Oct 2026 (payments switched to Cashfree; image-generation notes added)_

---

## 1. The idea

An app where couples gift each other poems, presented as an animated, anime-style image/video with romantic background music.

- Users write their own poem **or** generate a romantic one with generative AI.
- Share the result to **Instagram Stories / WhatsApp Status**.
- Optionally send a **physical printed card** to the loved one's address, with flowers and chocolate.
- The card is shaped like a **prepaid card**, so it can later carry real gift-card value.
- Stated objective: let people share their feelings through poems (not only romance — anniversaries, apologies, gratitude, etc.).

---

## 2. Roadmap

| Phase | Scope | Notes |
|---|---|---|
| **0 – Validate** | Landing page, waitlist, hand-made samples, talk to 10–20 couples | No app needed |
| **1 – MVP (digital only)** | Signup, write/AI-generate poem, template-based animation, music, export video, share link | **Built as a scaffold** |
| **2 – Physical card** | Printed card with QR code to the digital poem, flowers/chocolate add-ons, shipping | Start in one city; use print and delivery partners |
| **3 – Real gift-card value** | Load real money onto the card | Needs a card-issuing partner, KYC/compliance, legal advice. Treat as its own 6–12 month project |
| **4 – Growth** | Fully generative AI video, memory timeline, occasion reminders, premium tiers | After the template approach is validated |

Key advice: validate the "AI poem + animation + share" loop first, before cards, shipping, or compliance.

---

## 3. Tech stack decisions

| Area | Choice |
|---|---|
| Mobile app | **React Native (Expo, TypeScript)** - decided; scaffold in `mobile/`. Chosen over Flutter and native Kotlin: one codebase for Android + iOS, shares skills with the React-based Remotion render service, good JS support for Firebase/Cloudflare. Test Instagram Stories sharing early with a small prototype. |
| Backend | Python **FastAPI** (built) |
| Database | **PostgreSQL** via SQLAlchemy (built), hosted on **Neon** (decided; chosen over Supabase because it's plain Postgres and auth/storage are already covered by Firebase and R2); Redis planned for caching/sessions, not added yet |
| AI poem generation | Claude API; 3 variants per request, user can edit/regenerate |
| Animation | Pre-built template animations (Lottie/Rive) for the MVP, not generative video |
| Video rendering | Planned: **Remotion** (React-based) or FFmpeg, as a separate render service |
| Media storage + CDN | **Cloudflare R2 + CDN** (zero egress fees suit a share-heavy app) |
| Music | Licensed library (Epidemic Sound / Artlist); do not use unlicensed popular songs |
| Payments | Cashfree (was Razorpay in the first scaffold) |
| Auth | **Firebase Auth** (phone OTP) - decided. Currently a stub in `backend/app/routers/auth.py`; backend should verify Firebase ID tokens. |
| Analytics | PostHog or Mixpanel, tracking the create → share funnel |

### Data model (Phase 1)
`users`, `partners`, `poems`, `poem_variants`, `templates`, `music_tracks`, `creations`, `shares`, plus `credit_packs` and `credit_transactions`. A planned `orders` table (Phase 2) is not built yet.

`creations` is separate from `poems` so the same words can be reused with a different template or music, and so the expensive render step stays isolated.

---

## 4. Payments and app-store commission

### Indian gateways
Razorpay, Cashfree, PayU and CCAvenue can accept both Indian and international payments. Razorpay and Cashfree were noted as holding RBI cross-border (PA-CB) authorisation. **Confirm current status directly with the gateway you pick**, since this changes.

### Google Play commission
- Google takes a commission on **digital goods consumed in the app** that are bought inside the app.
- **Physical goods and services** (card, flowers, chocolate delivery) do **not** need Play Billing, so Razorpay can be used directly.
- In India, an alternative billing system like Razorpay is allowed, but the Google fee is only reduced slightly (about 4 points), not removed.
- Rates and rules are changing in 2026 (reduced rates in some regions), so **re-check the current Play policy before launch**.

### Decision: Cashfree is the payment gateway (replaces Razorpay)
Decided later in the project: the backend and `web-checkout/credits.html` now use **Cashfree** instead of Razorpay. Cashfree has no client-side signature, so `/credits/checkout/verify` fetches the order status from Cashfree and credits only if it is PAID; the webhook is signed with the client secret. The client was written without access to Cashfree's docs and has **not been tested against the Cashfree sandbox**; verify endpoints, API version, webhook format and JS SDK calls first. Cashfree also requires a 10-digit customer phone, so real phone collection at signup is a follow-up.

### Decision: credits bought outside the app
- Story generation is priced in **credits** (1 credit ≈ ₹1; default cost 5 credits per story, adjustable).
- Credits are bought on a **standalone web checkout page** (`web-checkout/credits.html`) hosted on its own domain, opened in the device browser or Chrome Custom Tabs (not an in-app WebView).
- After payment the backend confirms the order with the gateway, credits the wallet, and redirects back via a deep link (`tweezers://credits-success`). A webhook is the backup source of truth. Crediting is idempotent (no double credit).
- Open point: even with this setup, confirm Google's current "steering" rules before relying on it.

### Current state: everything is free
`PAYMENTS_ENABLED` defaults to `false`. While off, story generation needs no credits and the checkout endpoints return 503. Nothing was deleted; set `PAYMENTS_ENABLED=true` and redeploy to switch charging back on.

---

## 5. Naming and branding

- Names brainstormed: Feelverse, Heartlines, Versify, Verz, Rhymewell, Kindred, and others.
- **Sarovar** (Hindi/Sanskrit for "lake") was explored in depth. Caveat noted: Sarovar Hotels is an established Indian brand, so a proper trademark check was advised.
- Logo directions were designed for Sarovar: ripple mark, lotus ripple, wave monogram, moonlake, and an illustrated circular badge.
- **Project and app were then renamed to "Tweezers"** (code, docker config, deep link scheme, README).
- **Open item:** the logo boards still say "sarovar" with lake/lotus imagery. They need a redo for Tweezers (new direction or just a wordmark swap).
- **Decision: the name stays "Tweezers"** (repo is `twizzers`, but "Twizzers" was rejected: too close to the Twizzlers candy brand). Tagline / theme: **"Two bodies, one soul"** (Hindi: "do jism, ek jaan"). Alternatives considered: Ek Jaan, Ekatma, Dohaa, Jodi. Open item: trademark and domain check for "Tweezers".

---

## 5b. Future idea: AI image generation (to look at in future implementations)

Question raised: can Meta AI be used for image generation?

- **Meta AI / "Imagine"** is a consumer product (WhatsApp, Instagram, meta.ai). As far as we know it has **no public image-generation API**, so it can't be called from the backend, and scraping it would break Meta's terms. Meta's research image models (e.g. Emu) are not offered as a production API either. The Llama API is believed to cover text and image *understanding*, not generation. Re-check Meta's developer docs before ruling it out.
- **Fits the roadmap:** the MVP uses pre-made Lottie/Rive templates; generative visuals belong to Phase 4, after the template approach is validated.
- **Realistic options when we get there:**
  - Hosted open models (FLUX / Stable Diffusion, with anime-style checkpoints) via Replicate, fal.ai or Together: usually cheapest, pay per image, fits the per-story credits model.
  - Self-hosted open model on a GPU: cheaper at scale, more ops work.
  - OpenAI image API or Google Imagen: high quality, higher cost per image.
- **Possible design:** a new `backend/app/images.py` next to `ai.py` with a stub fallback (like the demo poem text), generated images stored in Cloudflare R2 and used as the background in the Remotion render step.
- **Open decision:** which provider; compare price per image, anime-style quality, content-safety controls and India latency.

---

## 6. Database

- **PostgreSQL** is the database. Docker Compose runs Postgres 16; the backend connects through `DATABASE_URL`.
- Tables are now created by Alembic migrations (`alembic upgrade head`), no longer by `create_all`. The scaffold's create, credits (mocked Cashfree) and Firebase-login flows have been run against a real Postgres 16.

### Alembic migrations
Alembic tracks database structure changes in versioned files, like Git for the schema.

- **Why:** `create_all` never alters existing tables. If you add a column after launch, it won't appear, and fixing that by deleting tables would delete user data.
- **How:** change `models.py` → `alembic revision --autogenerate` → `alembic upgrade head`. Each migration can be undone with `alembic downgrade`.
- **When:** not needed for throwaway local data. Add it **before real users or the first deployment**; after that, every table change goes through a migration.

---

## 7. Hosting plan (not yet deployed)

| Piece | Suggested host |
|---|---|
| Backend API | Render, Railway or Fly.io (check for a region near India) |
| Database | **Neon** (managed Postgres, decided). Use a region close to the API host and India users; set `DATABASE_URL` with `?sslmode=require`. Scale-to-zero adds a cold-start delay: fine for testing, disable on a paid plan before launch. Re-check pricing/free-tier limits. |
| Videos and images | Cloudflare R2 + CDN |
| Credits checkout page | Cloudflare Pages (static file, own domain such as `pay.yourdomain.com`) |
| Video rendering | Separate worker server, or Remotion Lambda on AWS |
| Mobile app | Google Play (App Store later) |

Alternative: everything on AWS Mumbai (ap-south-1) for best India latency, at more setup effort and usually higher cost.

**Before going live:** keep secrets in the host's environment settings, tighten CORS (currently allows all origins), replace the signup stub with real auth, and use a public HTTPS domain for the payment webhook. Check current pricing and free tiers.

---

## 8. What exists today

`tweezers.zip` contains:

- `backend/` — FastAPI + PostgreSQL API: auth stub, poems (write / AI-generate / pick variant), templates, music, creations with public share links, credits and Cashfree checkout (switched off), seed script, Dockerfile
- `frontend-demo/index.html` — browser page that walks through the create flow
- `web-checkout/credits.html` — standalone credits purchase page
- `docker-compose.yml` — Postgres + backend
- `docs/PROJECT_DISCUSSION.md` — this file (now in the twizzers repo)

**Tested:** signup → generate poem → pick variant → template and music → create → public share link; credits purchase and signature checks; free mode.

**Stubbed:** video rendering (placeholder URL), real OTP auth, real template and music files.

---

## 9. Next steps (suggested order)

1. ~~Add Alembic and generate the first migration.~~ Done (`backend/alembic/`, migration `0001`).
2. ~~Build the render service (Remotion).~~ Built and run end to end locally (`render-service/`); still to do: R2 upload, deployment, real templates and music.
3. Build the **mobile app** (React Native / Expo, scaffold done in `mobile/`) against the existing API.
4. Firebase phone-OTP login: backend token verification done (`/auth/firebase`); routes are now protected with `get_current_user` and ownership checks, and `/auth/signup` is dev-only (`AUTH_DEV_BYPASS`). Still to do: the app's login screen.
5. Add deployment config (API host, Neon, Cloudflare).
6. Redo the **Tweezers logo/brand**; check trademark and domain.
7. Phase 0 validation: landing page, waitlist, hand-made samples.
8. Test the Cashfree integration against the sandbox.
9. Later: AI image generation (see 5b).
10. Later: `orders` table and physical card flow (Phase 2).
