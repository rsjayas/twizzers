import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, ai
from ..database import get_db

router = APIRouter(prefix="/poems", tags=["poems"])

# How many credits one AI story generation costs. 1 credit = Rs 1 by
# convention (matches the credit pack pricing in seed_data.py), so this
# maps directly to the Rs 1-10 per story range discussed.
COST_PER_STORY_CREDITS = int(os.getenv("COST_PER_STORY_CREDITS", "5"))

# Feature flag: while False, story generation is completely free - no
# credit check, no deduction. Flip to "true" in the environment whenever
# you're ready to turn payments back on; no code changes needed.
PAYMENTS_ENABLED = os.getenv("PAYMENTS_ENABLED", "false").lower() == "true"


@router.post("/generate", response_model=schemas.PoemOut)
async def generate_poem(payload: schemas.PoemGenerateRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == payload.user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    if PAYMENTS_ENABLED and (user.credits_balance or 0) < COST_PER_STORY_CREDITS:
        raise HTTPException(
            402,
            f"Not enough credits. This costs {COST_PER_STORY_CREDITS} credits, "
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
        user_id=payload.user_id,
        source="ai_generated",
        original_prompt=payload.model_dump(exclude={"user_id"}),
        status="draft",
    )
    db.add(poem)
    db.flush()  # get poem.id before commit

    for text in variants_text:
        db.add(models.PoemVariant(poem_id=poem.id, variant_text=text))

    # Deduct credits only after generation succeeds, so a failed AI call
    # never charges the user. Skipped entirely while payments are off.
    if PAYMENTS_ENABLED:
        user.credits_balance = (user.credits_balance or 0) - COST_PER_STORY_CREDITS

    db.commit()
    db.refresh(poem)
    return poem


@router.post("/write", response_model=schemas.PoemOut)
def write_poem(payload: schemas.PoemWriteRequest, db: Session = Depends(get_db)):
    poem = models.Poem(
        user_id=payload.user_id,
        source="written",
        content=payload.content,
        status="finalized",
    )
    db.add(poem)
    db.commit()
    db.refresh(poem)
    return poem


@router.post("/{poem_id}/select-variant", response_model=schemas.PoemOut)
def select_variant(poem_id: str, payload: schemas.PoemSelectVariantRequest, db: Session = Depends(get_db)):
    poem = db.query(models.Poem).filter(models.Poem.id == poem_id).first()
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
def get_poem(poem_id: str, db: Session = Depends(get_db)):
    poem = db.query(models.Poem).filter(models.Poem.id == poem_id).first()
    if not poem:
        raise HTTPException(404, "Poem not found")
    return poem
