"""
Cashfree Payments (PG) integration for the credits web checkout.

Requires CASHFREE_CLIENT_ID and CASHFREE_CLIENT_SECRET env vars.
Get test keys from the Cashfree merchant dashboard (Developers > API Keys).
CASHFREE_ENV is "sandbox" (default) or "production".

Talks to Cashfree's Orders API with httpx and verifies webhooks with
stdlib hmac - no Cashfree SDK dependency.

Flow: create_order() returns a payment_session_id that the web checkout
page hands to Cashfree's JS SDK. Cashfree has no client-side signature, so
after checkout the backend confirms by fetching the order (get_order) and
checking order_status == "PAID". The webhook is the backup source of truth.
"""
import os
import hmac
import hashlib
import base64
import httpx

CASHFREE_CLIENT_ID = os.getenv("CASHFREE_CLIENT_ID", "")
CASHFREE_CLIENT_SECRET = os.getenv("CASHFREE_CLIENT_SECRET", "")
CASHFREE_ENV = os.getenv("CASHFREE_ENV", "sandbox").lower()
CASHFREE_API_VERSION = os.getenv("CASHFREE_API_VERSION", "2023-08-01")
# Optional: if set, sent as order_meta.notify_url (otherwise configure the
# webhook URL in the Cashfree dashboard).
CASHFREE_NOTIFY_URL = os.getenv("CASHFREE_NOTIFY_URL", "")

_BASE_URLS = {
    "sandbox": "https://sandbox.cashfree.com/pg",
    "production": "https://api.cashfree.com/pg",
}
CASHFREE_BASE_URL = _BASE_URLS.get(CASHFREE_ENV, _BASE_URLS["sandbox"])


class CashfreeError(Exception):
    pass


def _headers() -> dict:
    if not CASHFREE_CLIENT_ID or not CASHFREE_CLIENT_SECRET:
        raise CashfreeError(
            "CASHFREE_CLIENT_ID / CASHFREE_CLIENT_SECRET not configured. "
            "Set them as environment variables before creating real orders."
        )
    return {
        "x-client-id": CASHFREE_CLIENT_ID,
        "x-client-secret": CASHFREE_CLIENT_SECRET,
        "x-api-version": CASHFREE_API_VERSION,
        "Content-Type": "application/json",
    }


async def create_order(
    order_id: str,
    amount_inr: int,
    customer_id: str,
    customer_phone: str,
    customer_email: str | None = None,
    note: str | None = None,
) -> dict:
    """
    Creates a Cashfree order. The amount is in rupees and the order_id is
    chosen by us (must be unique).
    Returns the raw order object (contains 'order_id', 'payment_session_id', ...)
    """
    body = {
        "order_id": order_id,
        "order_amount": amount_inr,
        "order_currency": "INR",
        "customer_details": {
            "customer_id": customer_id,
            "customer_phone": customer_phone,
        },
    }
    if customer_email:
        body["customer_details"]["customer_email"] = customer_email
    if note:
        body["order_note"] = note
    if CASHFREE_NOTIFY_URL:
        body["order_meta"] = {"notify_url": CASHFREE_NOTIFY_URL}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(f"{CASHFREE_BASE_URL}/orders", headers=_headers(), json=body)
        if resp.status_code >= 400:
            raise CashfreeError(f"Cashfree order creation failed: {resp.status_code} {resp.text}")
        return resp.json()


async def get_order(order_id: str) -> dict:
    """Fetches an order; 'order_status' is "PAID" once payment succeeded."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{CASHFREE_BASE_URL}/orders/{order_id}", headers=_headers())
        if resp.status_code >= 400:
            raise CashfreeError(f"Cashfree order fetch failed: {resp.status_code} {resp.text}")
        return resp.json()


def verify_webhook_signature(raw_body: bytes, timestamp: str, signature: str) -> bool:
    """
    Verifies Cashfree webhook payloads (headers x-webhook-timestamp and
    x-webhook-signature). signature = base64(HMAC_SHA256(timestamp + raw_body,
    client_secret)). Cashfree signs with the same secret key used for API calls.
    """
    if not CASHFREE_CLIENT_SECRET:
        raise CashfreeError("CASHFREE_CLIENT_SECRET not configured.")
    message = timestamp.encode() + raw_body
    digest = hmac.new(CASHFREE_CLIENT_SECRET.encode(), message, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode()
    return hmac.compare_digest(expected, signature)
