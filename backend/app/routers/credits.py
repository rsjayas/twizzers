import os
import datetime as dt
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session

from .. import models, schemas, cashfree_client
from ..database import get_db

router = APIRouter(prefix="/credits", tags=["credits"])

# Same flag as app/routers/poems.py - keeps both in sync from one place.
PAYMENTS_ENABLED = os.getenv("PAYMENTS_ENABLED", "false").lower() == "true"


@router.get("/packs", response_model=List[schemas.CreditPackOut])
def list_packs(db: Session = Depends(get_db)):
    return db.query(models.CreditPack).filter(models.CreditPack.is_active == True).all()  # noqa: E712


@router.get("/balance/{user_id}", response_model=schemas.CreditBalanceOut)
def get_balance(user_id: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    return schemas.CreditBalanceOut(user_id=user.id, credits_balance=user.credits_balance)


@router.post("/checkout/create-order", response_model=schemas.CreateCheckoutOrderResponse)
async def create_checkout_order(payload: schemas.CreateCheckoutOrderRequest, db: Session = Depends(get_db)):
    """
    Called by the standalone web checkout page (NOT from inside the app)
    to start a Cashfree order for a credit pack purchase.
    """
    if not PAYMENTS_ENABLED:
        raise HTTPException(503, "Payments are not enabled yet - everything is free for now.")

    user = db.query(models.User).filter(models.User.id == payload.user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    pack = db.query(models.CreditPack).filter(
        models.CreditPack.id == payload.credit_pack_id,
        models.CreditPack.is_active == True,  # noqa: E712
    ).first()
    if not pack:
        raise HTTPException(404, "Credit pack not found")

    txn = models.CreditTransaction(
        user_id=user.id,
        credit_pack_id=pack.id,
        credits=pack.credits,
        amount_inr=pack.price_inr,
        status="created",
    )
    db.add(txn)
    db.flush()

    # Cashfree requires a 10-digit customer phone; fall back to a placeholder
    # for users who haven't given one (auth is still a stub).
    digits = "".join(c for c in (user.phone or "") if c.isdigit())[-10:]
    phone = digits if len(digits) == 10 else "9999999999"

    cf_order_id = f"credit_txn_{txn.id}"
    try:
        order = await cashfree_client.create_order(
            order_id=cf_order_id,
            amount_inr=pack.price_inr,
            customer_id=user.id,
            customer_phone=phone,
            customer_email=user.email,
            note=f"{pack.credits} credits",
        )
    except cashfree_client.CashfreeError as e:
        txn.status = "failed"
        db.commit()
        raise HTTPException(502, str(e))
    txn.cashfree_order_id = order["order_id"]
    db.commit()

    return schemas.CreateCheckoutOrderResponse(
        transaction_id=txn.id,
        cashfree_order_id=order["order_id"],
        payment_session_id=order["payment_session_id"],
        cashfree_env=cashfree_client.CASHFREE_ENV,
        amount_inr=pack.price_inr,
        credits=pack.credits,
    )


def _credit_wallet_if_needed(db: Session, txn: models.CreditTransaction) -> models.User:
    """Idempotent: only credits the wallet once, even if called twice
    (e.g. both the client verify call AND the webhook fire for the same payment)."""
    user = db.query(models.User).filter(models.User.id == txn.user_id).first()
    if txn.status != "paid":
        txn.status = "paid"
        txn.paid_at = dt.datetime.utcnow()
        user.credits_balance = (user.credits_balance or 0) + txn.credits
        db.commit()
        db.refresh(user)
    return user


@router.post("/checkout/verify", response_model=schemas.VerifyPaymentResponse)
async def verify_payment(payload: schemas.VerifyPaymentRequest, db: Session = Depends(get_db)):
    """
    Called by the web checkout page after Cashfree's checkout reports
    completion. Cashfree has no client-side signature, so we ask Cashfree
    directly for the order status; only a PAID order for the right amount
    credits the wallet. Returns the new balance so the page can show it
    before redirecting back into the app.
    """
    txn = db.query(models.CreditTransaction).filter(models.CreditTransaction.id == payload.transaction_id).first()
    if not txn:
        raise HTTPException(404, "Transaction not found")
    if txn.cashfree_order_id != payload.cashfree_order_id:
        raise HTTPException(400, "Order ID mismatch")

    try:
        order = await cashfree_client.get_order(txn.cashfree_order_id)
    except cashfree_client.CashfreeError as e:
        raise HTTPException(502, str(e))

    if order.get("order_status") != "PAID" or float(order.get("order_amount", 0)) != float(txn.amount_inr):
        # Not paid (yet). Don't mark failed: the user may still complete
        # payment, and the webhook can still credit later.
        raise HTTPException(400, f"Payment not confirmed (status: {order.get('order_status')})")

    user = _credit_wallet_if_needed(db, txn)

    return schemas.VerifyPaymentResponse(
        status="paid",
        credits_added=txn.credits,
        new_balance=user.credits_balance,
    )


@router.post("/webhook")
async def cashfree_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_webhook_signature: str = Header(default=""),
    x_webhook_timestamp: str = Header(default=""),
):
    """
    Server-to-server confirmation from Cashfree. Configure this URL
    (https://yourdomain.com/credits/webhook) in the Cashfree dashboard
    (Developers > Webhooks), subscribed to the payment success event.

    This is the SOURCE OF TRUTH for crediting the wallet - it covers the
    case where the user's browser closes right after paying, before the
    client-side verify call or redirect can fire.
    """
    raw_body = await request.body()

    if not cashfree_client.CASHFREE_CLIENT_SECRET:
        raise HTTPException(503, "Cashfree is not configured")
    if not cashfree_client.verify_webhook_signature(raw_body, x_webhook_timestamp, x_webhook_signature):
        raise HTTPException(400, "Invalid webhook signature")

    payload = await request.json()
    event = payload.get("type")
    if event != "PAYMENT_SUCCESS_WEBHOOK":
        return {"ok": True, "ignored_event": event}

    data = payload["data"]
    order_id = data["order"]["order_id"]
    payment_id = str(data["payment"]["cf_payment_id"])

    txn = db.query(models.CreditTransaction).filter(models.CreditTransaction.cashfree_order_id == order_id).first()
    if not txn:
        return {"ok": False, "reason": "transaction not found for order"}

    txn.cashfree_payment_id = payment_id
    _credit_wallet_if_needed(db, txn)
    return {"ok": True}
