#!/usr/bin/env python3
"""
Checks that a running local stack works end to end. Uses only the Python standard library.

    python scripts/smoke_local.py
    python scripts/smoke_local.py --api http://localhost:8000 --admin-email admin@example.com --admin-password local-admin-password

Needs the API running with AUTH_DEV_BYPASS=true and the seed data loaded. If the render service is
configured, it waits for the real video. Exit code 0 means everything passed.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid

results = []


def call(base, method, path, body=None, token=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            ctype = resp.headers.get("content-type", "")
            return resp.status, (json.loads(raw) if "json" in ctype else raw.decode(errors="replace"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, raw
    except (urllib.error.URLError, OSError) as e:
        return 0, str(e)


def check(name, ok, detail=""):
    ok = bool(ok)
    results.append(ok)
    print(("PASS  " if ok else "FAIL  ") + name + (f"  ({detail})" if detail and not ok else ""))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--admin-email", default="")
    ap.add_argument("--admin-password", default="")
    ap.add_argument("--timeout", type=int, default=420, help="seconds to wait for the video render")
    a = ap.parse_args()
    base = a.api.rstrip("/")

    status, body = call(base, "GET", "/health")
    if not check("API is up (/health)", status == 200, f"{status} {body}"):
        print("\nStart the stack first: docker compose up --build")
        return 1

    email = f"smoke-{uuid.uuid4().hex[:8]}@example.com"
    status, user = call(base, "POST", "/auth/signup", {"email": email, "name": "Smoke Test"})
    if not check("Dev signup", status == 200, f"{status} {user} (set AUTH_DEV_BYPASS=true)"):
        return 1
    token = f"dev:{user['id']}"

    status, templates = call(base, "GET", "/templates/")
    _, tracks = call(base, "GET", "/music/")
    check("Templates and music are seeded", status == 200 and templates and tracks,
          "run: docker compose exec backend python seed_data.py")
    if not (templates and tracks):
        return 1

    status, poem = call(base, "POST", "/poems/generate", {"occasion": "gratitude", "tone": "playful"}, token)
    check("Generate poem (3 variants)", status == 200 and len(poem.get("variants", [])) == 3, f"{status} {poem}")

    status, written = call(base, "POST", "/poems/write",
                           {"content": "You are my sunrise,\nmy quiet night,\nmy every reason\nto hold on tight."}, token)
    check("Write own poem", status == 200 and written.get("status") == "finalized", f"{status} {written}")
    if status != 200:
        return 1

    status, creation = call(base, "POST", "/creations/",
                            {"poem_id": written["id"], "template_id": templates[0]["id"], "music_track_id": tracks[0]["id"]}, token)
    check("Create video job", status == 200, f"{status} {creation}")
    if status != 200:
        return 1

    waited, last = 0, creation
    start = time.time()
    while last["status"] == "rendering" and time.time() - start < a.timeout:
        time.sleep(4)
        _, last = call(base, "GET", f"/creations/{creation['id']}", token=token)
        if int(time.time() - start) % 20 < 4:
            print(f"      ...rendering ({int(time.time() - start)}s)")
    check("Video is ready", last.get("status") == "ready", f"status {last.get('status')} after {int(time.time() - start)}s; see the render container logs")

    if last.get("status") == "ready" and last.get("rendered_video_url"):
        url = last["rendered_video_url"]
        placeholder = "cdn.example.com" in url
        if placeholder:
            print("      (placeholder video URL: the render service is not configured, so no real video was made)")
        else:
            ok = False
            for candidate in (url, url.replace("10.0.2.2", "localhost")):
                try:
                    with urllib.request.urlopen(candidate, timeout=30) as r:
                        ok = r.status == 200 and len(r.read(200000)) > 10000
                except (urllib.error.URLError, OSError):
                    continue
                if ok:
                    break
            check("Video file downloads", ok, url)

    status, page = call(base, "GET", f"/v/{last['share_link_slug']}")
    check("Public share page shows the poem", status == 200 and "sunrise" in str(page), f"{status}")

    if a.admin_email and a.admin_password:
        status, login = call(base, "POST", "/admin/api/login", {"email": a.admin_email, "password": a.admin_password})
        if check("Admin login", status == 200, f"{status} {login}"):
            status, stats = call(base, "GET", "/admin/api/stats", token=login["token"])
            check("Admin dashboard stats", status == 200 and stats["totals"]["creations"] >= 1, f"{status}")
        status, ui = call(base, "GET", "/admin/")
        check("Admin web app is served at /admin/", status == 200 and "root" in str(ui), "build the admin UI (docker does this)")

    passed = sum(results)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
