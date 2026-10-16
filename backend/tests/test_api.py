import base64
import hashlib
import hmac
import json
from unittest import mock


def _ids(client):
    return client.get("/templates/").json()[0]["id"], client.get("/music/").json()[0]["id"]


def test_routes_require_login(client):
    for method, path in [("post", "/poems/generate"), ("post", "/poems/write"), ("post", "/creations/"),
                         ("get", "/credits/balance"), ("post", "/credits/checkout/create-order")]:
        r = getattr(client, method)(path, **({"json": {}} if method == "post" else {}))
        assert r.status_code == 401, path
    assert client.get("/templates/").status_code == 200
    assert client.get("/credits/packs").status_code == 200


def test_create_flow_and_ownership(client, make_user):
    _, ha = make_user(credits=10)
    _, hb = make_user()
    poem = client.post("/poems/generate", json={"occasion": "anniversary", "tone": "playful"}, headers=ha).json()
    assert len(poem["variants"]) == 3
    assert client.get("/credits/balance", headers=ha).json()["credits_balance"] == 5  # 5 credits per poem
    assert client.get(f"/poems/{poem['id']}", headers=hb).status_code == 404
    variant = poem["variants"][0]["id"]
    assert client.post(f"/poems/{poem['id']}/select-variant", json={"variant_id": variant}, headers=hb).status_code == 404
    client.post(f"/poems/{poem['id']}/select-variant", json={"variant_id": variant}, headers=ha)

    t, m = _ids(client)
    body = {"poem_id": poem["id"], "template_id": t, "music_track_id": m}
    assert client.post("/creations/", json=body, headers=hb).status_code == 400
    creation = client.post("/creations/", json=body, headers=ha).json()
    assert creation["status"] == "ready"  # no render service in tests: placeholder URL
    assert client.get(f"/creations/{creation['id']}", headers=hb).status_code == 404
    assert client.post("/creations/share-event", json={"creation_id": creation["id"], "channel": "link"}, headers=hb).status_code == 404
    assert client.post("/creations/share-event", json={"creation_id": creation["id"], "channel": "link"}, headers=ha).status_code == 200
    assert client.get(f"/creations/share/{creation['share_link_slug']}").status_code == 200


def test_not_enough_credits(client, make_user):
    _, h = make_user(credits=0)
    r = client.post("/poems/generate", json={"occasion": "apology", "tone": "nostalgic"}, headers=h)
    assert r.status_code == 402


def test_viewer_page_escapes_poem(client, make_user):
    _, h = make_user()
    poem = client.post("/poems/write", json={"content": "Hi <script>alert(1)</script>"}, headers=h).json()
    t, m = _ids(client)
    c = client.post("/creations/", json={"poem_id": poem["id"], "template_id": t, "music_track_id": m}, headers=h).json()
    page = client.get(f"/v/{c['share_link_slug']}")
    assert page.status_code == 200 and "text/html" in page.headers["content-type"]
    assert "<script>alert" not in page.text and "&lt;script&gt;" in page.text
    assert client.get("/v/does-not-exist").status_code == 404


def test_render_callback_needs_secret(client, make_user):
    _, h = make_user()
    poem = client.post("/poems/write", json={"content": "x y z"}, headers=h).json()
    t, m = _ids(client)
    c = client.post("/creations/", json={"poem_id": poem["id"], "template_id": t, "music_track_id": m}, headers=h).json()
    url = f"/creations/internal/{c['id']}/render-result"
    assert client.post(url, json={"status": "failed"}, headers={"x-render-secret": "wrong"}).status_code == 401
    ok = client.post(url, json={"status": "ready", "video_url": "https://cdn/x.mp4", "thumbnail_url": "https://cdn/x.jpg"},
                     headers={"x-render-secret": "render-secret"})
    assert ok.status_code == 200
    assert client.get(f"/creations/{c['id']}", headers=h).json()["rendered_video_url"] == "https://cdn/x.mp4"


def test_credits_purchase_flow(client, make_user):
    from app import cashfree_client as cf

    user_id, h = make_user()
    pack = client.get("/credits/packs").json()[0]
    state = {"status": "ACTIVE"}

    async def fake_create(order_id, amount_inr, **kw):
        return {"order_id": order_id, "payment_session_id": "sess"}

    async def fake_get(order_id):
        return {"order_status": state["status"], "order_amount": pack["price_inr"]}

    _, other = make_user()
    with mock.patch.object(cf, "create_order", fake_create), mock.patch.object(cf, "get_order", fake_get):
        order = client.post("/credits/checkout/create-order", json={"credit_pack_id": pack["id"]}, headers=h).json()
        body = {"transaction_id": order["transaction_id"], "cashfree_order_id": order["cashfree_order_id"]}
        assert client.post("/credits/checkout/verify", json=body, headers=h).status_code == 400  # not paid yet
        state["status"] = "PAID"
        assert client.post("/credits/checkout/verify", json=body, headers=other).status_code == 404  # not theirs
        assert client.post("/credits/checkout/verify", json=body, headers=h).status_code == 200
        client.post("/credits/checkout/verify", json=body, headers=h)  # idempotent

        raw = json.dumps({"type": "PAYMENT_SUCCESS_WEBHOOK",
                          "data": {"order": {"order_id": order["cashfree_order_id"]}, "payment": {"cf_payment_id": 1}}}).encode()
        ts = "1700000000"
        sig = base64.b64encode(hmac.new(b"test-secret", ts.encode() + raw, hashlib.sha256).digest()).decode()
        bad = client.post("/credits/webhook", content=raw, headers={"x-webhook-signature": "x", "x-webhook-timestamp": ts})
        assert bad.status_code == 400
        good = client.post("/credits/webhook", content=raw, headers={"x-webhook-signature": sig, "x-webhook-timestamp": ts})
        assert good.json()["ok"]

    assert client.get("/credits/balance", headers=h).json()["credits_balance"] == pack["credits"]  # credited once


def test_security_headers_and_cors(client, make_user):
    r = client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
    _, h = make_user()
    assert client.get("/credits/balance", headers=h).headers["cache-control"] == "no-store"

    allowed = client.options("/credits/packs", headers={"Origin": "https://pay.example.com", "Access-Control-Request-Method": "GET"})
    assert allowed.headers.get("access-control-allow-origin") == "https://pay.example.com"
    blocked = client.options("/credits/packs", headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in blocked.headers


def test_origin_verify_header_when_configured(client, monkeypatch):
    monkeypatch.setenv("ORIGIN_VERIFY_SECRET", "cdn-shared-secret-123")
    assert client.get("/templates/").status_code == 403
    assert client.get("/templates/", headers={"X-Origin-Verify": "wrong"}).status_code == 403
    assert client.get("/templates/", headers={"X-Origin-Verify": "cdn-shared-secret-123"}).status_code == 200
    assert client.get("/health").status_code == 200  # uptime checks stay open
    monkeypatch.delenv("ORIGIN_VERIFY_SECRET")
    assert client.get("/templates/").status_code == 200
