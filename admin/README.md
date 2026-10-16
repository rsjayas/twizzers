# Tweezers admin dashboard

React + Vite + TypeScript web app for staff: dashboard charts, users and credit adjustments, creations (retry, take down, restore), transactions, templates/music/credit packs, runtime settings, admin accounts and the audit log. Screens and buttons depend on the signed-in admin's role.

It has no hosting of its own: the backend serves the built files at `/admin` (same domain as the API) and the API at `/admin/api`.

## Screens
- **Dashboard:** totals, activity per day (sign-ups, poems, videos, shares), revenue, how far people get (sign up, poem, video, share), shares by channel, most used styles and music, render failure rate, open reports.
- **Users:** search; sign-in methods; credit adjustments; **block / unblock**; **erase data** (privacy request); CSV export.
- **Creations:** retry failed renders, take down and restore videos.
- **Reports:** viewers can report a video from its public page; admins take it down (closes every open report on that video) or dismiss.
- **Poems:** search poem text for moderation.
- **Transactions:** payments and manual credit changes, CSV export.
- **Content:** templates, music and credit packs.
- **Settings:** payments on/off, credits per poem, new sign-ups open/closed, welcome credits for new accounts. Changes apply immediately, no redeploy.
- **System:** is the database, render service and each integration configured and reachable, failed or stuck renders, safety switches (dev login, CDN check, CORS), and plain-language warnings.
- **Admins** (superadmin): add admins, change roles, disable, reset passwords, switch off someone's two-factor login.
- **Audit log** (superadmin): every change, filterable by admin and action.
- **My account:** change password; **two-factor login** with an authenticator app (QR code).

## Roles
| Role | Can |
|---|---|
| `superadmin` | everything, including settings, admin accounts, the audit log, erasing user data |
| `support` | users, credit adjustments, block/unblock, retry renders, take down / restore videos, reports, CSV exports |
| `content` | templates, music, credit packs (everyone can view all read-only screens) |

## First admin
Set `ADMIN_JWT_SECRET` (16+ random characters) on the backend, then create the first admin. Locally, `.env` can create one on start (`ADMIN_BOOTSTRAP_EMAIL` / `ADMIN_BOOTSTRAP_PASSWORD`, only when no superadmin exists). Otherwise (there is no default account):

```bash
docker compose exec backend python -m app.admin.cli create-admin you@example.com superadmin
```

Open `http://localhost:8000/admin/`.

## Develop
```bash
cd admin
npm install
npm run dev        # http://localhost:5173/admin/, API calls proxied to localhost:8000
npm run build      # outputs dist/, served by the backend when present (ADMIN_UI_DIR)
npm run typecheck
```

Notes: the login token is kept in `sessionStorage` (cleared when the tab closes). The backend limits failed logins (5 per 15 minutes, in memory per process) and re-checks role and active status on every request. Put `/admin` behind an IP allowlist or VPN at your host if you can. There are no automated UI tests; the API is covered by `backend/tests/test_admin.py`.
