# Tweezers admin dashboard

React + Vite + TypeScript web app for staff: dashboard charts, users and credit adjustments, creations (retry, take down, restore), transactions, templates/music/credit packs, runtime settings, admin accounts and the audit log. Screens and buttons depend on the signed-in admin's role.

It has no hosting of its own: the backend serves the built files at `/admin` (same domain as the API) and the API at `/admin/api`.

## Roles
| Role | Can |
|---|---|
| `superadmin` | everything, including settings, admin accounts and the audit log |
| `support` | users, credit adjustments, retry renders, take down / restore videos |
| `content` | templates, music, credit packs |

## First admin
Set `ADMIN_JWT_SECRET` (16+ random characters) on the backend, then create the first admin (there is no default account):

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
