
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, ai, settings_store
from ..database import get_db
from ..firebase_auth import get_current_user

router = APIRouter(prefix="/poems", tags=["poems"])

# Credit price per generation and the payments switch come from app/settings_store.py
# (env defaults, overridable from the admin dashboard without a redeploy).


@router.post("/generate", response_model=schemas.PoemOut)
async def generate_poem(
    payload: schemas.PoemGenerateRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    payments_enabled = settings_store.get_value(db, "payments_enabled")
    cost = settings_store.get_value(db, "cost_per_story_credits")
    if payments_enabled and (user.credits_balance or 0) < cost:
        raise HTTPException(
            402,
            f"Not enough credits. This costs {cost} credits, "
            f"you have {user.credits_balance or 0}. Buy more credits to continue.",
        )

    variants_text = await ai.generate_poem_variants(
        occasion=payload.occasion,
        tone=payload.tone,
        relationship_length=payload.relationship_length,
        detail_1=payload.detail_1,
        detail_2=payload.detail_2,
        recipient_nickname=payload.recipient_nickname,
    )

    poem = models.Poem(
        user_id=user.id,
        source="ai_generated",
        original_prompt=payload.model_dump(),
        status="draft",
    )
    db.add(poem)
    db.flush()  # get poem.id before commit

    for text in variants_text:
        db.add(models.PoemVariant(poem_id=poem.id, variant_text=text))

    # Deduct credits only after generation succeeds, so a failed AI call
    # never charges the user. Skipped entirely while payments are off.
    if payments_enabled:
        user.credits_balance = (user.credits_balance or 0) - cost

    db.commit()
    db.refresh(poem)
    return poem


@router.post("/write", response_model=schemas.PoemOut)
def write_poem(
    payload: schemas.PoemWriteRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    poem = models.Poem(
        user_id=user.id,
        source="written",
        content=payload.content,
        status="finalized",
    )
    db.add(poem)
    db.commit()
    db.refresh(poem)
    return poem


@router.post("/{poem_id}/select-variant", response_model=schemas.PoemOut)
def select_variant(
    poem_id: str,
    payload: schemas.PoemSelectVariantRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    poem = db.query(models.Poem).filter(models.Poem.id == poem_id, models.Poem.user_id == user.id).first()
    if not poem:
        raise HTTPException(404, "Poem not found")

    variant = db.query(models.PoemVariant).filter(
        models.PoemVariant.id == payload.variant_id,
        models.PoemVariant.poem_id == poem_id,
    ).first()
    if not variant:
        raise HTTPException(404, "Variant not found")

    for v in poem.variants:
        v.selected = (v.id == variant.id)

    poem.content = variant.variant_text
    poem.status = "finalized"
    db.commit()
    db.refresh(poem)
    return poem


@router.get("/{poem_id}", response_model=schemas.PoemOut)
def get_poem(poem_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    poem = db.query(models.Poem).filter(models.Poem.id == poem_id, models.Poem.user_id == user.id).first()
    if not poem:
        raise HTTPException(404, "Poem not found")
    return poem
