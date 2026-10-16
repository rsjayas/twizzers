import itertools

import pyotp

from app import models
from app.admin import security
from app.database import SessionLocal

_ip = itertools.count(1)


def _creation(client, make_user):
    uid, h = make_user()
    poem = client.post("/poems/write", json={"content": "a poem\nfor testing"}, headers=h).json()
    t = client.get("/templates/").json()[0]["id"]
    m = client.get("/music/").json()[0]["id"]
    c = client.post("/creations/", json={"poem_id": poem["id"], "template_id": t, "music_track_id": m}, headers=h).json()
    return uid, h, c


def _fresh_ip():
    return {"x-forwarded-for": f"198.51.100.{next(_ip)}"}


def test_block_and_unblock_user(client, make_admin, make_user):
    _, support, _ = make_admin("support")
    _, content, _ = make_admin("content")
    uid, h = make_user()
    reason = {"reason": "abusive poems"}
    assert client.post(f"/admin/api/users/{uid}/block", json=reason, headers=content).status_code == 403
    blocked = client.post(f"/admin/api/users/{uid}/block", json=reason, headers=support).json()
    assert blocked["is_blocked"] is True and blocked["blocked_reason"] == "abusive poems"
    r = client.post("/poems/write", json={"content": "hello there"}, headers=h)
    assert r.status_code == 403 and r.json()["detail"] == "account_blocked"
    client.post(f"/admin/api/users/{uid}/unblock", json={"reason": "appeal accepted"}, headers=support)
    assert client.post("/poems/write", json={"content": "hello there"}, headers=h).status_code == 200


def test_erase_user_removes_content_but_keeps_payment_records(client, make_admin, make_user):
    _, boss, _ = make_admin("superadmin")
    _, support, _ = make_admin("support")
    uid, h, c = _creation(client, make_user)
    client.post(f"/admin/api/users/{uid}/credits", json={"delta": 5, "reason": "test credits"}, headers=boss)
    body = {"reason": "privacy request", "confirm_user_id": uid}
    assert client.post(f"/admin/api/users/{uid}/erase", json=body, headers=support).status_code == 403
    assert client.post(f"/admin/api/users/{uid}/erase", json={**body, "confirm_user_id": "wrong"}, headers=boss).status_code == 400
    done = client.post(f"/admin/api/users/{uid}/erase", json=body, headers=boss).json()
    assert done["creations"] == 1 and done["poems"] == 1
    assert client.get(f"/v/{c['share_link_slug']}").status_code == 404  # public link is gone
    user = client.get(f"/admin/api/users/{uid}", headers=boss).json()
    assert user["deleted"] is True and user["email"] is None and user["phone"] is None
    assert user["creations"] == [] and any(t["status"] == "adjusted" for t in user["transactions"])
    assert client.get("/credits/balance", headers=h).status_code == 401  # erased account cannot sign in
    assert client.post(f"/admin/api/users/{uid}/erase", json=body, headers=boss).status_code == 400  # only once


def test_signup_switch_and_welcome_credits(client, make_admin, make_user):
    _, boss, _ = make_admin("superadmin")
    try:
        client.put("/admin/api/settings", json={"welcome_credits": 12}, headers=boss)
        uid, h = make_user()
        assert client.get("/credits/balance", headers=h).json()["credits_balance"] == 12
        detail = client.get(f"/admin/api/users/{uid}", headers=boss).json()
        assert any(t["note"] == "Welcome credits" for t in detail["transactions"])

        client.put("/admin/api/settings", json={"signups_enabled": False}, headers=boss)
        closed = client.post("/auth/signup", json={"email": "closed@example.com"})
        assert closed.status_code == 403 and closed.json()["detail"] == "signups_closed"
        assert client.get("/credits/balance", headers=h).status_code == 200  # existing users carry on
    finally:
        client.put("/admin/api/settings", json={"welcome_credits": 0, "signups_enabled": True}, headers=boss)


def test_reports_flow(client, make_admin, make_user):
    _, support, _ = make_admin("support")
    _, content, _ = make_admin("content")
    _, _, c = _creation(client, make_user)
    slug = c["share_link_slug"]
    viewer = _fresh_ip()

    assert "Report this video" in client.get(f"/v/{slug}").text
    assert client.post(f"/v/{slug}/report", json={"reason": "bogus"}, headers=viewer).status_code == 422
    assert client.post("/v/nope/report", json={"reason": "spam"}, headers=viewer).status_code == 404
    assert client.post(f"/v/{slug}/report", json={"reason": "harassment", "details": "rude"}, headers=viewer).json() == {"ok": True}
    client.post(f"/v/{slug}/report", json={"reason": "harassment"}, headers=viewer)  # duplicate from the same person
    other = _fresh_ip()
    client.post(f"/v/{slug}/report", json={"reason": "spam"}, headers=other)

    listed = client.get("/admin/api/reports?status=open", headers=support).json()
    mine = [r for r in listed["items"] if r["creation_id"] == c["id"]]
    assert len(mine) == 2  # the duplicate was ignored

    rid = mine[0]["id"]
    assert client.post(f"/admin/api/reports/{rid}/resolve", json={"action": "takedown"}, headers=content).status_code == 403
    assert client.post(f"/admin/api/reports/{rid}/resolve", json={"action": "delete"}, headers=support).status_code == 400
    resolved = client.post(f"/admin/api/reports/{rid}/resolve", json={"action": "takedown", "note": "violates rules"}, headers=support).json()
    assert resolved["status"] == "actioned"
    assert client.get(f"/v/{slug}").status_code == 404
    still_open = [r for r in client.get("/admin/api/reports?status=open", headers=support).json()["items"] if r["creation_id"] == c["id"]]
    assert still_open == []  # every report on that video was closed together
    assert client.post(f"/admin/api/reports/{rid}/resolve", json={"action": "dismiss"}, headers=support).status_code == 400


def test_report_dismiss_and_rate_limit(client, make_admin, make_user):
    _, support, _ = make_admin("support")
    spammer = _fresh_ip()
    slugs = [_creation(client, make_user)[2]["share_link_slug"] for _ in range(6)]
    for slug in slugs[:5]:
        assert client.post(f"/v/{slug}/report", json={"reason": "spam"}, headers=spammer).status_code == 200
    assert client.post(f"/v/{slugs[5]}/report", json={"reason": "spam"}, headers=spammer).status_code == 429

    report = client.get("/admin/api/reports?status=open&limit=1", headers=support).json()["items"][0]
    dismissed = client.post(f"/admin/api/reports/{report['id']}/resolve", json={"action": "dismiss"}, headers=support).json()
    assert dismissed["status"] == "dismissed"
    assert client.get(f"/v/{report['creation']['share_link_slug']}").status_code == 200  # video stays up


def test_poems_list_and_search(client, make_admin, make_user):
    _, support, _ = make_admin("support")
    _, h = make_user()
    client.post("/poems/write", json={"content": "findable-needle-xyz in a poem"}, headers=h)
    found = client.get("/admin/api/poems?q=findable-needle-xyz", headers=support).json()
    assert found["total"] == 1 and found["items"][0]["status"] == "finalized"


def test_system_status_and_stats_extras(client, make_admin, make_user):
    _, support, _ = make_admin("support")
    uid, h, c = _creation(client, make_user)
    client.post("/creations/share-event", json={"creation_id": c["id"], "channel": "whatsapp"}, headers=h)

    system = client.get("/admin/api/system", headers=support).json()
    assert system["database_ok"] is True and system["render_service"]["configured"] is False
    assert any("AUTH_DEV_BYPASS" in w for w in system["warnings"])  # tests run with the dev bypass on
    assert set(system["attention"]) == {"open_reports", "failed_renders_24h", "stuck_renders"}

    stats = client.get("/admin/api/stats?days=7", headers=support).json()
    assert stats["funnel"]["shared"] >= 1 and stats["funnel"]["made_a_video"] >= 1
    assert any(row["name"] == "whatsapp" for row in stats["shares_by_channel"])
    assert stats["top_templates"] and "render_failure_rate" in stats and "open_reports" in stats["totals"]
    assert "shares" in stats["daily"][0]


def test_csv_exports(client, make_admin, make_user):
    _, boss, _ = make_admin("superadmin")
    _, content, _ = make_admin("content")
    uid, h = make_user()
    db = SessionLocal()
    db.query(models.User).filter(models.User.id == uid).update({"name": "=HYPERLINK(\"http://evil\")"})
    db.commit()
    db.close()
    client.post(f"/admin/api/users/{uid}/credits", json={"delta": 3, "reason": "export test"}, headers=boss)

    assert client.get("/admin/api/export/users.csv", headers=content).status_code == 403
    users = client.get("/admin/api/export/users.csv", headers=boss)
    assert users.headers["content-type"].startswith("text/csv") and "attachment" in users.headers["content-disposition"]
    assert users.text.splitlines()[0].startswith("id,name,email,phone")
    assert "'=HYPERLINK" in users.text and ",=HYPERLINK" not in users.text  # formula text is neutralised
    txns = client.get("/admin/api/export/transactions.csv", headers=boss)
    assert txns.text.splitlines()[0].startswith("id,user_id,status,credits") and ",adjusted,3," in txns.text
    audit_actions = [a["action"] for a in client.get("/admin/api/audit?action=export", headers=boss).json()["items"]]
    assert "export.users" in audit_actions and "export.transactions" in audit_actions


def test_change_own_password(client, make_admin):
    _, headers, email = make_admin("support")
    try:
        assert client.post("/admin/api/me/password", json={"current_password": "wrong-password", "new_password": "a-new-long-password"}, headers=headers).status_code == 400
        assert client.post("/admin/api/me/password", json={"current_password": "correct-horse-battery", "new_password": "short"}, headers=headers).status_code == 422
        assert client.post("/admin/api/me/password", json={"current_password": "correct-horse-battery", "new_password": "a-new-long-password"}, headers=headers).status_code == 200
        assert client.post("/admin/api/login", json={"email": email, "password": "correct-horse-battery"}).status_code == 401
        assert client.post("/admin/api/login", json={"email": email, "password": "a-new-long-password"}).status_code == 200
    finally:
        security._failures.clear()


def test_two_factor_login(client, make_admin):
    _, boss, _ = make_admin("superadmin")
    admin_id, headers, email = make_admin("support")
    pw = "correct-horse-battery"
    try:
        assert client.post("/admin/api/me/2fa/setup", json={"password": "wrong"}, headers=headers).status_code == 400
        setup = client.post("/admin/api/me/2fa/setup", json={"password": pw}, headers=headers).json()
        assert setup["otpauth_uri"].startswith("otpauth://totp/")
        totp = pyotp.TOTP(setup["secret"])
        # not active until a code is confirmed
        assert client.post("/admin/api/login", json={"email": email, "password": pw}).status_code == 200
        assert client.post("/admin/api/me/2fa/enable", json={"code": "000000"}, headers=headers).status_code == 400
        assert client.post("/admin/api/me/2fa/enable", json={"code": totp.now()}, headers=headers).json()["totp_enabled"] is True

        needs = client.post("/admin/api/login", json={"email": email, "password": pw})
        assert needs.status_code == 401 and needs.json()["detail"] == "2fa_required"
        assert client.post("/admin/api/login", json={"email": email, "password": pw, "code": "000000"}).status_code == 401
        ok = client.post("/admin/api/login", json={"email": email, "password": pw, "code": totp.now()})
        assert ok.status_code == 200 and ok.json()["admin"]["totp_enabled"] is True

        # a superadmin can switch it off for someone who lost their phone
        reset = client.patch(f"/admin/api/admins/{admin_id}", json={"reset_2fa": True}, headers=boss)
        assert reset.json()["totp_enabled"] is False
        assert client.post("/admin/api/login", json={"email": email, "password": pw}).status_code == 200
    finally:
        security._failures.clear()


def test_audit_log_filters(client, make_admin):
    _, boss, boss_email = make_admin("superadmin")
    client.post("/admin/api/admins", json={"email": "filter-me@test.example", "password": "long-enough-password", "role": "content"}, headers=boss)
    by_action = client.get("/admin/api/audit?action=admin.create", headers=boss).json()
    assert by_action["total"] >= 1 and all(r["action"].startswith("admin.create") for r in by_action["items"])
    by_admin = client.get(f"/admin/api/audit?admin_email={boss_email}", headers=boss).json()
    assert by_admin["total"] >= 1 and all(boss_email in r["admin_email"] for r in by_admin["items"])
