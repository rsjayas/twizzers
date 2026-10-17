# Running Tweezers on your own computer

Everything runs locally: Postgres, the API with the admin dashboard, the video renderer and the mobile app. No cloud accounts are needed. A Claude API key is optional (without it you get demo poems).

The Docker builds could not be run where this guide was written (no Docker there), so the first `docker compose up --build` on your machine is the first real test of them. If it fails, send the error output.

## 1. What to install
- **Docker Desktop** (Windows or Mac) or Docker Engine with the Compose plugin (Linux). Give Docker at least **6 GB of memory** and 2+ CPUs in its settings: the video renderer peaks at about 1.6 GB and is slow on one CPU.
- **Git**.
- **Node.js 22** (for the mobile app).
- **Python 3** (only to run the smoke test; any recent version).
- For the app: an **Android emulator** (Android Studio) or a real Android phone with the **Expo Go** app.

## 2. Start the backend
```bash
git clone <your repo url> && cd twizzers
git checkout claude/epic-gates-5rqbqc
cp .env.example .env
```
Edit `.env`:
- `ANTHROPIC_API_KEY=` your key from console.anthropic.com (optional).
- `RENDER_PUBLIC_URL=` where the phone downloads videos from: `http://10.0.2.2:4000` for the Android emulator, or `http://<your computer's LAN IP>:4000` for a real phone (find the IP with `ipconfig` on Windows or `ifconfig` on Mac/Linux).

Then:
```bash
docker compose up --build
```
The first build takes several minutes (it downloads Chrome for the renderer). On start the API runs the database migrations, creates the first admin and loads the placeholder templates, music and credit packs.

| What | Where |
|---|---|
| API docs | http://localhost:8000/docs |
| Admin dashboard | http://localhost:8000/admin/ (email `admin@example.com`, password `local-admin-password`, from `.env`) |
| Renderer health | http://localhost:4000/health |

Stop with Ctrl+C. `docker compose down` keeps your data; `docker compose down -v` wipes the database.

## 3. Check that everything works
```bash
python scripts/smoke_local.py --admin-email admin@example.com --admin-password local-admin-password
```
It signs up a test user, generates and writes poems, makes a video (waits for the real render, a few minutes), downloads it, opens the public share page and logs into the admin API. All lines should say `PASS`. A failing line says what to look at.

## 4. Run the mobile app (dev mode, no Firebase needed)
```bash
cd mobile
cp .env.example .env
npm install
npx expo start --go
```
In `mobile/.env` set `EXPO_PUBLIC_API_URL`:
- Android emulator: `http://10.0.2.2:8000` (the default).
- Real phone on the same Wi-Fi: `http://<your computer's LAN IP>:8000`. On Windows allow ports 8000 and 4000 through the firewall.

Scan the QR code with Expo Go. Dev login accepts any email and checks no password. The flow: sign in, write or generate a poem, pick a variant, choose style and music, wait for the video, share the link. Also try My videos, and My account (sign out, delete account). To see credits, turn payments on under Settings in the admin dashboard (the app then shows a credits chip and the price).

Real Firebase login (email + password, Google) needs a development build instead of Expo Go: see `mobile/README.md`.

## 5. Other things to try
- **Admin dashboard:** charts and funnel, users (block, erase, export), creations, reports, poems, content, settings, system status, admin accounts, audit log, two-factor login under My account. Sign in with the account above; create more admins under Admins to try the `support` and `content` roles. To try moderation: open a video's share page (`/v/<slug>`), use "Report this video", then find it under Reports.
- **Demo web page:** open `frontend-demo/index.html` in a browser (set the API address on the page).
- **Payments:** off by default (everything free). Turn them on under Settings in the admin dashboard. A real purchase needs Cashfree sandbox keys in `.env` (`CASHFREE_CLIENT_ID`, `CASHFREE_CLIENT_SECRET`) and has never been tried against Cashfree.
- **Tests:**
  - Backend (needs a Postgres test database): `cd backend && pip install -r requirements.txt -r requirements-dev.txt && TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/tweezers_test pytest`
  - Admin app: `cd admin && npm install && npm run typecheck`
  - Mobile app: `cd mobile && npx tsc --noEmit`

## 6. If something goes wrong
| Problem | Likely cause |
|---|---|
| Port 5432, 8000 or 4000 already in use | Stop the other program, or change the port in `docker-compose.yml`. |
| Render container exits or the video never finishes | Docker has too little memory or CPU (see section 1). Look at `docker compose logs render`. Renders take about 2 to 6 minutes. |
| The app cannot reach the API | Wrong `EXPO_PUBLIC_API_URL` (emulator vs phone), different Wi-Fi, or a firewall. Open `http://<that address>:8000/health` in the phone's browser to test. |
| Video downloads fail on the phone | `RENDER_PUBLIC_URL` in `.env` is wrong for your device; change it and run `docker compose up -d`. |
| "Dev login failed" in the app | `AUTH_DEV_BYPASS` is not `true` in `.env`. |
| Admin login fails or "not configured" | `ADMIN_JWT_SECRET` missing in `.env`, or the bootstrap admin was not created (it is only created when no superadmin exists). |
| Need a fresh start | `docker compose down -v`, then `docker compose up --build`. |

## 7. Without Docker
Install Postgres, then follow "Run without Docker" in `CLAUDE.md`: create the database, set `DATABASE_URL`, `alembic upgrade head`, `python seed_data.py`, `uvicorn app.main:app --reload` in `backend/`, and `npm start` in `render-service/` (set `RENDER_SECRET`). Build the admin UI once with `cd admin && npm install && npm run build` so `/admin` works.
