import os
import datetime as dt
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session

from .. import models, schemas, razorpay_client
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
    to start a Razorpay order for a credit pack purchase.
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

    order = await razorpay_client.create_order(
        amount_inr=pack.price_inr,
        receipt=f"credit_txn_{txn.id}",
        notes={"user_id": user.id, "credit_pack_id": pack.id, "transaction_id": txn.id},
    )
    txn.razorpay_order_id = order["id"]
    db.commit()

    return schemas.CreateCheckoutOrderResponse(
        transaction_id=txn.id,
        razorpay_order_id=order["id"],
        razorpay_key_id=razorpay_client.RAZORPAY_KEY_ID,
        amount_paise=order["amount"],
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
def verify_payment(payload: schemas.VerifyPaymentRequest, db: Session = Depends(get_db)):
    """
    Called by the web checkout page immediately after Razorpay's client-side
    checkout succeeds. Confirms the signature, credits the wallet, and
    returns the new balance so the page can show it before redirecting
    back into the app.
    """
    txn = db.query(models.CreditTransaction).filter(models.CreditTransaction.id == payload.transaction_id).first()
    if not txn:
        raise HTTPException(404, "Transaction not found")
    if txn.razorpay_order_id != payload.razorpay_order_id:
        raise HTTPException(400, "Order ID mismatch")

    valid = razorpay_client.verify_payment_signature(
        order_id=payload.razorpay_order_id,
        payment_id=payload.razorpay_payment_id,
        signature=payload.razorpay_signature,
    )
    if not valid:
        txn.status = "failed"
        db.commit()
        raise HTTPException(400, "Payment signature verification failed")

    txn.razorpay_payment_id = payload.razorpay_payment_id
    user = _credit_wallet_if_needed(db, txn)

    return schemas.VerifyPaymentResponse(
        status="paid",
        credits_added=txn.credits,
        new_balance=user.credits_balance,
    )


@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_razorpay_signature: str = Header(default=""),
):
    """
    Server-to-server confirmation from Razorpay. Configure this URL
    (https://yourdomain.com/credits/webhook) in the Razorpay dashboard,
    subscribed to the 'payment.captured' event.

    This is the SOURCE OF TRUTH for crediting the wallet - it covers the
    case where the user's browser closes right after paying, before the
    client-side verify call or redirect can fire.
    """
    import os
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
    raw_body = await request.body()

    if webhook_secret:
        valid = razorpay_client.verify_webhook_signature(raw_body, x_razorpay_signature, webhook_secret)
        if not valid:
            raise HTTPException(400, "Invalid webhook signature")

    payload = await request.json()
    event = payload.get("event")
    if event != "payment.captured":
        return {"ok": True, "ignored_event": event}

    order_id = payload["payload"]["payment"]["entity"]["order_id"]
    payment_id = payload["payload"]["payment"]["entity"]["id"]

    txn = db.query(models.CreditTransaction).filter(models.CreditTransaction.razorpay_order_id == order_id).first()
    if not txn:
        return {"ok": False, "reason": "transaction not found for order"}

    txn.razorpay_payment_id = payment_id
    _credit_wallet_if_needed(db, txn)
    return {"ok": True}
