# Security and exposure

What is public, what must not be, and how to harden an EC2 deployment. Pricing figures are third-party and unverified (16 Oct 2026).

## What is internet-facing
| Piece | Public? |
|---|---|
| API (HTTPS), including the Cashfree webhook and the `/v/<slug>` share page | Yes, required |
| Admin dashboard (`/admin`, served by the API) | Same address; protected by its own login; also restrict by IP, VPN or Cloudflare Access if possible |
| Videos (R2 + CDN) | Yes, public read; anyone with a link can watch |
| Render service | Should be private: only the API calls it. Protected by `RENDER_SECRET` if it must be public |
| Database (Neon) | Public address, TLS + password; IP allowlist if the plan allows it |

## Is a bare EC2 machine on the internet "vulnerable"?
Not by default, but nothing protects it until you configure it. The usual causes of a compromise on a small server are: SSH open to the world with a weak or leaked key, an unpatched operating system, a database or admin port exposed, secrets left in files or code, and bugs in the app.

### Server checklist (EC2)
- Security group: inbound only 80 and 443 (and 443 only from the CDN, see below). No SSH from the internet; use AWS Systems Manager Session Manager, or SSH only from your own IP with key login and no passwords.
- Do not publish Postgres (5432) or the render port (4000): remove those `ports:` lines from `docker-compose.yml` in production (they exist for local testing). We use Neon, so there is no database on the machine.
- Require IMDSv2 on the instance (blocks a common credential-theft attack).
- Turn on automatic security updates for the operating system and rebuild the images regularly for dependency updates.
- Run containers as an unprivileged user (done for the API image; the render image still runs as root and the Dockerfiles have not been built or tested).
- Keep secrets in the host's secret store or environment, never in git. `AUTH_DEV_BYPASS` must be `false`.
- AWS account: MFA on the root account, no root access keys, least-privilege IAM, billing alerts, CloudWatch alarms on CPU and status checks.
- Snapshots are optional because data lives in Neon and R2.

## Putting CloudFront in front of EC2
Yes, it works. It hides the origin, gives free HTTPS certificates (ACM), absorbs basic floods, and lets you add AWS WAF.

1. Give the EC2 machine a domain name for the origin (for example `origin.example.com`) with a real certificate (Caddy with Let's Encrypt is the simplest). CloudFront with "HTTPS only" to the origin needs a valid certificate for that name.
2. Create a distribution with that origin; viewer HTTPS with an ACM certificate (issued in us-east-1 for CloudFront); redirect HTTP to HTTPS.
3. API paths must not be cached: use the managed "CachingDisabled" cache policy and an origin request policy that forwards all headers except Host (so `Authorization` reaches the API), allowing all methods (POST is needed for the Cashfree webhook). Static files (`/admin/` assets, `/static/`) can be cached.
4. Add a custom origin header `X-Origin-Verify: <long random secret>` in the distribution and set `ORIGIN_VERIFY_SECRET` to the same value on the server. The API then returns 403 to anything without it, so hitting the EC2 address directly does not work. `/health` stays open for uptime checks. Use HTTPS to the origin so the header is not sent in clear.
5. Restrict the EC2 security group's inbound 443 to the AWS managed prefix list for CloudFront origin-facing addresses. That prefix list is shared by every CloudFront customer, so the secret header is what really proves traffic came through your distribution.
6. Optional: AWS WAF on the distribution (extra monthly and per-request cost) for rate limits and common attack rules.

Cost: CloudFront reportedly has an always-free tier of 1 TB of data transfer and 10 million requests a month; beyond that, India data transfer is about $0.11 per GB and HTTPS requests about $0.012-0.017 per 10,000 (sources conflict). Our API responses are small, so the free tier should cover early launch. A newer flat-rate plan structure was mentioned by one source and not confirmed.

Cloudflare's free proxy is a simpler alternative that does the same job (hidden origin, HTTPS, basic protection) and we already use Cloudflare for R2. The `X-Origin-Verify` header works with it too (a Cloudflare "Transform Rule" adds the header).

## What the app already does
- Every user route needs a Firebase token and checks ownership; admin routes need an admin token with role checks and an audit log; the payment webhook checks its signature.
- Security headers on every response, no caching of auth, credits and admin API responses.
- CORS is limited to `CORS_ORIGINS` (empty means none; local dev with `AUTH_DEV_BYPASS=true` allows all).
- Optional `ORIGIN_VERIFY_SECRET` check (above).
- Admin login throttling (in memory, per process), bcrypt passwords, optional two-factor login (authenticator app) per admin, roles re-checked on every request, every change in the audit log.
- Public "report this video" on the share page, limited to 5 reports an hour per reporter and one per video per day; admins can block users and take videos down.
- Admin CSV exports neutralise spreadsheet formulas and are logged.
- Poem text on the share page is HTML-escaped.

## Known gaps
- No general rate limit on the API (use CloudFront/Cloudflare/WAF rules or the host's limits).
- Admin login throttling is per process, so it is weaker with several servers.
- The render service image runs as root; Docker images are not built or scanned yet.
- No dependency vulnerability scanning in CI (there is no CI yet).
- Share-link videos are public by URL (random names, but not private).
- Erasing a user removes database records but not video files already in storage (R2).
- The reporter limit uses the client IP from `X-Forwarded-For`; if the API is reachable directly (no CDN in front, `ORIGIN_VERIFY_SECRET` unset) that header can be faked.
