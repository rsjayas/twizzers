from app.admin import security


def _creation(client, make_user):
    uid, h = make_user()
    poem = client.post("/poems/write", json={"content": "a poem\nfor you"}, headers=h).json()
    t = client.get("/templates/").json()[0]["id"]
    m = client.get("/music/").json()[0]["id"]
    c = client.post("/creations/", json={"poem_id": poem["id"], "template_id": t, "music_track_id": m}, headers=h).json()
    return uid, h, c


def test_admin_login_and_throttle(client, make_admin):
    _, _, email = make_admin("support")
    try:
        assert client.post("/admin/api/login", json={"email": email, "password": "wrong"}).status_code == 401
        assert client.post("/admin/api/login", json={"email": "nobody@test.example", "password": "x"}).status_code == 401
        ok = client.post("/admin/api/login", json={"email": email, "password": "correct-horse-battery"})
        assert ok.status_code == 200 and ok.json()["admin"]["role"] == "support"
        token = ok.json()["token"]
        assert client.get("/admin/api/me", headers={"Authorization": f"Bearer {token}"}).json()["email"] == email
        for _ in range(5):
            client.post("/admin/api/login", json={"email": email, "password": "wrong"})
        assert client.post("/admin/api/login", json={"email": email, "password": "correct-horse-battery"}).status_code == 429
    finally:
        security._failures.clear()


def test_admin_routes_need_a_token(client, make_user):
    assert client.get("/admin/api/stats").status_code == 401
    assert client.get("/admin/api/stats", headers={"Authorization": "Bearer nonsense"}).status_code == 401
    _, user_headers = make_user()  # an app user's token is not an admin token
    assert client.get("/admin/api/stats", headers=user_headers).status_code == 401


def test_stats_users_and_credit_adjustment(client, make_admin, make_user):
    _, support, _ = make_admin("support")
    _, content, _ = make_admin("content")
    uid, _ = make_user(credits=10)

    stats = client.get("/admin/api/stats?days=7", headers=support).json()
    assert len(stats["daily"]) == 7 and "users" in stats["totals"]

    assert any(u["id"] == uid for u in client.get(f"/admin/api/users?q={uid}", headers=support).json()["items"])
    detail = client.get(f"/admin/api/users/{uid}", headers=support).json()
    assert detail["credits_balance"] == 10

    body = {"delta": 5, "reason": "goodwill refund"}
    assert client.post(f"/admin/api/users/{uid}/credits", json=body, headers=content).status_code == 403
    assert client.post(f"/admin/api/users/{uid}/credits", json=body, headers=support).json()["credits_balance"] == 15
    assert client.post(f"/admin/api/users/{uid}/credits", json={"delta": -100, "reason": "too much"}, headers=support).status_code == 400
    assert client.post(f"/admin/api/users/{uid}/credits", json={"delta": 0, "reason": "nothing"}, headers=support).status_code in (400, 422)
    txns = client.get(f"/admin/api/users/{uid}", headers=support).json()["transactions"]
    assert any(t["status"] == "adjusted" and t["note"] == "goodwill refund" for t in txns)


def test_takedown_hides_public_link_and_restore(client, make_admin, make_user):
    _, support, _ = make_admin("support")
    _, content, _ = make_admin("content")
    _, _, c = _creation(client, make_user)
    slug = c["share_link_slug"]
    assert client.get(f"/v/{slug}").status_code == 200

    reason = {"reason": "reported content"}
    assert client.post(f"/admin/api/creations/{c['id']}/takedown", json=reason, headers=content).status_code == 403
    assert client.post(f"/admin/api/creations/{c['id']}/takedown", json=reason, headers=support).json()["status"] == "removed"
    assert client.get(f"/v/{slug}").status_code == 404
    assert client.get(f"/creations/share/{slug}").status_code == 404
    assert client.post(f"/admin/api/creations/{c['id']}/restore", json=reason, headers=support).json()["status"] == "ready"
    assert client.get(f"/v/{slug}").status_code == 200


def test_retry_needs_render_service_and_failed_status(client, make_admin, make_user):
    _, support, _ = make_admin("support")
    _, _, c = _creation(client, make_user)  # status ready
    assert client.post(f"/admin/api/creations/{c['id']}/retry", headers=support).status_code == 400
    client.post(f"/creations/internal/{c['id']}/render-result", json={"status": "failed"},
                headers={"x-render-secret": "render-secret"})
    assert client.post(f"/admin/api/creations/{c['id']}/retry", headers=support).status_code == 503  # none in tests


def test_content_management_by_role(client, make_admin):
    _, content, _ = make_admin("content")
    _, support, _ = make_admin("support")
    body = {"name": "Admin Template", "category": "test", "mood_tags": ["romantic"]}
    assert client.post("/admin/api/templates", json=body, headers=support).status_code == 403
    created = client.post("/admin/api/templates", json=body, headers=content).json()
    patched = client.patch(f"/admin/api/templates/{created['id']}", json={"is_active": False}, headers=content).json()
    assert patched["is_active"] is False and patched["name"] == "Admin Template"
    assert any(t["id"] == created["id"] for t in client.get("/admin/api/templates", headers=support).json())

    pack = client.post("/admin/api/packs", json={"label": "Mega", "credits": 500, "price_inr": 299}, headers=content).json()
    assert client.patch(f"/admin/api/packs/{pack['id']}", json={"price_inr": 0}, headers=content).status_code == 422
    track = client.post("/admin/api/music", json={"title": "New", "audio_file_url": "/static/music/x.mp3"}, headers=content).json()
    assert client.patch(f"/admin/api/music/{track['id']}", json={"title": "Newer"}, headers=content).json()["title"] == "Newer"


def test_settings_change_takes_effect_without_redeploy(client, make_admin, make_user):
    _, boss, _ = make_admin("superadmin")
    _, support, _ = make_admin("support")
    assert client.put("/admin/api/settings", json={"cost_per_story_credits": 1}, headers=support).status_code == 403
    assert client.put("/admin/api/settings", json={"cost_per_story_credits": -1}, headers=boss).status_code == 400

    _, h = make_user(credits=3)
    assert client.put("/admin/api/settings", json={"cost_per_story_credits": 3}, headers=boss).json()["cost_per_story_credits"] == 3
    poem = client.post("/poems/generate", json={"occasion": "gratitude", "tone": "playful"}, headers=h)
    assert poem.status_code == 200
    assert client.get("/credits/balance", headers=h).json()["credits_balance"] == 0

    client.put("/admin/api/settings", json={"payments_enabled": False}, headers=boss)  # free mode
    assert client.post("/poems/generate", json={"occasion": "gratitude", "tone": "playful"}, headers=h).status_code == 200
    client.put("/admin/api/settings", json={"payments_enabled": True, "cost_per_story_credits": 5}, headers=boss)  # restore


def test_admin_accounts_and_audit_log(client, make_admin):
    boss_id, boss, boss_email = make_admin("superadmin")
    _, support, _ = make_admin("support")
    assert client.get("/admin/api/admins", headers=support).status_code == 403
    assert client.get("/admin/api/audit", headers=support).status_code == 403

    new = client.post("/admin/api/admins", json={"email": "new@test.example", "password": "long-enough-password", "role": "support"}, headers=boss)
    assert new.status_code == 200
    assert client.post("/admin/api/admins", json={"email": "new@test.example", "password": "long-enough-password", "role": "support"}, headers=boss).status_code == 409
    assert client.post("/admin/api/admins", json={"email": "x@test.example", "password": "short", "role": "support"}, headers=boss).status_code == 422
    assert client.post("/admin/api/admins", json={"email": "y@test.example", "password": "long-enough-password", "role": "root"}, headers=boss).status_code == 400

    # you cannot lock yourself out or remove the last superadmin
    assert client.patch(f"/admin/api/admins/{boss_id}", json={"is_active": False}, headers=boss).status_code == 400

    # a disabled admin's existing token stops working immediately
    login = client.post("/admin/api/login", json={"email": "new@test.example", "password": "long-enough-password"}).json()
    headers = {"Authorization": f"Bearer {login['token']}"}
    assert client.get("/admin/api/me", headers=headers).status_code == 200
    client.patch(f"/admin/api/admins/{new.json()['id']}", json={"is_active": False}, headers=boss)
    assert client.get("/admin/api/me", headers=headers).status_code == 401

    actions = [a["action"] for a in client.get("/admin/api/audit?limit=100", headers=boss).json()["items"]]
    assert "admin.create" in actions and "admin.update" in actions
