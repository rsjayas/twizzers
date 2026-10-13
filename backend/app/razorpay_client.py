"""
Razorpay integration for the credits web checkout.

Requires RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET env vars.
Get test keys at https://dashboard.razorpay.com/app/keys

This module intentionally only talks to Razorpay's Orders API and does
signature verification - it does not depend on the razorpay SDK, just
httpx + stdlib hmac, to keep the dependency footprint small.
"""
import os
import hmac
import hashlib
import base64
import httpx

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_ORDERS_URL = "https://api.razorpay.com/v1/orders"


class RazorpayError(Exception):
    pass


async def create_order(amount_inr: int, receipt: str, notes: dict | None = None) -> dict:
    """
    Creates a Razorpay Order. Amount must be passed to Razorpay in paise
    (smallest currency unit), so amount_inr * 100.
    Returns the raw Razorpay order object (contains 'id', 'amount', etc.)
    """
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        raise RazorpayError(
            "RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET not configured. "
            "Set them as environment variables before creating real orders."
        )

    auth = base64.b64encode(f"{RAZORPAY_KEY_ID}:{RAZORPAY_KEY_SECRET}".encode()).decode()

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            RAZORPAY_ORDERS_URL,
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/json",
            },
            json={
                "amount": amount_inr * 100,
                "currency": "INR",
                "receipt": receipt,
                "notes": notes or {},
            },
        )
        if resp.status_code >= 400:
            raise RazorpayError(f"Razorpay order creation failed: {resp.status_code} {resp.text}")
        return resp.json()


def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """
    Verifies the signature Razorpay sends back after a successful checkout.
    Per Razorpay docs: signature = HMAC_SHA256(order_id + "|" + payment_id, key_secret)
    """
    if not RAZORPAY_KEY_SECRET:
        raise RazorpayError("RAZORPAY_KEY_SECRET not configured.")

    payload = f"{order_id}|{payment_id}".encode()
    expected = hmac.new(RAZORPAY_KEY_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_webhook_signature(raw_body: bytes, signature: str, webhook_secret: str) -> bool:
    """
    Verifies Razorpay webhook payloads (separate secret from the API key,
    configured in the Razorpay dashboard's webhook settings).
    Use this on the /credits/webhook endpoint for server-to-server
    confirmation, which is more reliable than relying on the client-side
    verify call alone (covers cases where the user closes the browser
    right after paying, before the redirect fires).
    """
    expected = hmac.new(webhook_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
