from app import render_client


def _make(client, headers, text="a poem\nfor you"):
    poem = client.post("/poems/write", json={"content": text}, headers=headers).json()
    t = client.get("/templates/").json()[0]["id"]
    m = client.get("/music/").json()[0]["id"]
    return client.post("/creations/", json={"poem_id": poem["id"], "template_id": t, "music_track_id": m}, headers=headers).json()


def test_public_config_follows_the_admin_settings(client, make_admin):
    _, boss, _ = make_admin("superadmin")
    try:
        cfg = client.get("/config").json()
        assert set(cfg) == {"payments_enabled", "cost_per_story_credits", "signups_enabled"}
        client.put("/admin/api/settings", json={"cost_per_story_credits": 9, "signups_enabled": False}, headers=boss)
        cfg = client.get("/config").json()
        assert cfg["cost_per_story_credits"] == 9 and cfg["signups_enabled"] is False
    finally:
        client.put("/admin/api/settings", json={"cost_per_story_credits": 5, "signups_enabled": True}, headers=boss)


def test_legal_pages_are_public_html(client, monkeypatch):
    monkeypatch.setenv("LEGAL_COMPANY_NAME", "<script>x</script> Ltd")
    for path, phrase in [("/privacy", "What we collect"), ("/terms", "What is not allowed"), ("/delete-account", "Delete my account")]:
        r = client.get(path)
        assert r.status_code == 200 and "text/html" in r.headers["content-type"] and phrase in r.text
    assert "<script>x</script>" not in client.get("/privacy").text  # company name is escaped
    monkeypatch.setenv("LEGAL_DRAFT_BANNER", "false")
    assert "Draft for review" not in client.get("/terms").text


def test_my_creations_lists_only_my_visible_videos(client, make_user, make_admin):
    _, support, _ = make_admin("support")
    uid, mine = make_user()
    _, other = make_user()
    first = _make(client, mine, "first poem")
    second = _make(client, mine, "second poem")
    _make(client, other, "someone else's poem")
    listed = client.get("/creations/mine", headers=mine).json()
    assert [c["id"] for c in listed] == [second["id"], first["id"]]  # newest first
    assert listed[0]["poem"] == "second poem" and "share_link_slug" in listed[0]
    client.post(f"/admin/api/creations/{first['id']}/takedown", json={"reason": "test removal"}, headers=support)
    assert [c["id"] for c in client.get("/creations/mine", headers=mine).json()] == [second["id"]]
    assert client.get("/creations/mine").status_code == 401


def test_user_deletes_own_account(client, make_user, monkeypatch):
    deleted = []
    monkeypatch.setattr(render_client, "delete_render_files", lambda ids: deleted.extend(ids))
    uid, h = make_user()
    c = _make(client, h)
    assert client.post("/auth/me/erase", json={"confirm": "delete"}, headers=h).status_code == 400
    done = client.post("/auth/me/erase", json={"confirm": "DELETE"}, headers=h)
    assert done.status_code == 200 and done.json() == {"ok": True, "creations": 1, "poems": 1}
    assert deleted == [c["id"]]  # the video files were deleted too
    assert client.get(f"/v/{c['share_link_slug']}").status_code == 404
    assert client.get("/credits/balance", headers=h).status_code == 401  # the account no longer works


def test_admin_erase_also_deletes_video_files(client, make_user, make_admin, monkeypatch):
    deleted = []
    monkeypatch.setattr(render_client, "delete_render_files", lambda ids: deleted.extend(ids))
    _, boss, _ = make_admin("superadmin")
    uid, h = make_user()
    c = _make(client, h)
    r = client.post(f"/admin/api/users/{uid}/erase", json={"reason": "privacy request", "confirm_user_id": uid}, headers=boss)
    assert r.status_code == 200 and deleted == [c["id"]]


def test_render_client_is_quiet_without_a_render_service(monkeypatch):
    monkeypatch.delenv("RENDER_SERVICE_URL", raising=False)
    render_client.delete_render_files(["abc"])  # no error, nothing to call
