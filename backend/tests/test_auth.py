"""Sign-in with email + password, Google and phone (Firebase), and how accounts are linked."""
from unittest import mock

import pytest

from app import firebase_auth


def claims(uid, provider, email=None, verified=True, phone=None):
    c = {"user_id": uid, "firebase": {"sign_in_provider": provider}}
    if email is not None:
        c.update(email=email, email_verified=verified)
    if phone:
        c["phone_number"] = phone
    return c


@pytest.fixture()
def tokens(client):
    """Register fake Firebase tokens: tokens['t1'] = claims(...)."""
    table = {}

    def fake_verify(token, request, audience=None):
        assert audience == "test-project"
        if token in table:
            return table[token]
        raise ValueError("bad token")

    with mock.patch.object(firebase_auth.google_id_token, "verify_firebase_token", fake_verify):
        yield table


def login(client, token, name=None):
    return client.post("/auth/firebase", json={"id_token": token, "name": name})


def test_invalid_token_is_rejected(client, tokens):
    assert login(client, "nope").status_code == 401


def test_email_password_needs_a_verified_email(client, tokens):
    tokens["pw1"] = claims("uid-pw-1", "password", "new.user@example.com", verified=False)
    blocked = login(client, "pw1")
    assert blocked.status_code == 403 and blocked.json()["detail"] == "email_not_verified"
    assert client.get("/auth/me", headers={"Authorization": "Bearer pw1"}).status_code == 403

    tokens["pw1"] = claims("uid-pw-1", "password", "new.user@example.com", verified=True)
    ok = login(client, "pw1", name="New User")
    assert ok.status_code == 200
    assert ok.json()["email"] == "new.user@example.com" and ok.json()["name"] == "New User"
    assert login(client, "pw1").json()["id"] == ok.json()["id"]  # same account every time
    assert client.get("/auth/me", headers={"Authorization": "Bearer pw1"}).json()["id"] == ok.json()["id"]


def test_google_and_password_with_the_same_verified_email_are_one_account(client, tokens):
    tokens["pw"] = claims("uid-link-pw", "password", "Both.Ways@Example.com")
    tokens["g"] = claims("uid-link-google", "google.com", "both.ways@example.com")
    first = login(client, "pw").json()
    second = login(client, "g").json()
    assert first["id"] == second["id"]  # not two accounts, even with different letter case

    from app import models
    from app.database import SessionLocal
    db = SessionLocal()
    providers = sorted(i.provider for i in db.query(models.UserIdentity).filter_by(user_id=first["id"]))
    db.close()
    assert providers == ["google.com", "password"]


def test_unverified_email_never_links_to_someone_elses_account(client, tokens):
    tokens["victim"] = claims("uid-victim", "google.com", "victim@example.com")
    victim = login(client, "victim").json()
    # An attacker registers the victim's address somewhere that does not prove ownership.
    tokens["attacker"] = claims("uid-attacker", "other", "victim@example.com", verified=False)
    attacker = login(client, "attacker").json()
    assert attacker["id"] != victim["id"]
    assert attacker["email"] is None


def test_phone_login_links_to_a_user_with_the_same_phone(client, tokens, make_user):
    uid, headers = make_user()
    phone = client.get("/auth/me", headers=headers)  # dev user exists; read its phone from the admin-free route
    from app import models
    from app.database import SessionLocal
    db = SessionLocal()
    number = db.query(models.User).filter_by(id=uid).first().phone
    db.close()
    tokens["ph"] = claims("uid-phone", "phone", phone=number)
    assert login(client, "ph").json()["id"] == uid


def test_existing_user_with_that_email_is_linked_when_verified(client, tokens):
    from app import models
    from app.database import SessionLocal
    db = SessionLocal()
    legacy = models.User(email="legacy@example.com", name="Legacy", credits_balance=7)
    db.add(legacy)
    db.commit()
    legacy_id = legacy.id
    db.close()
    tokens["l"] = claims("uid-legacy", "google.com", "legacy@example.com")
    out = login(client, "l").json()
    assert out["id"] == legacy_id
