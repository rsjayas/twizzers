from typing import Optional, List
from pydantic import BaseModel


class UserCreate(BaseModel):
    phone: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None


class FirebaseLoginRequest(BaseModel):
    id_token: str
    name: Optional[str] = None


class UserOut(BaseModel):
    id: str
    phone: Optional[str]
    email: Optional[str]
    name: Optional[str]

    class Config:
        from_attributes = True


class PoemGenerateRequest(BaseModel):
    user_id: str
    occasion: str          # e.g. "anniversary", "apology", "long_distance"
    tone: str               # e.g. "playful", "deeply_romantic", "nostalgic"
    relationship_length: Optional[str] = None
    detail_1: Optional[str] = None
    detail_2: Optional[str] = None
    recipient_nickname: Optional[str] = None


class PoemVariantOut(BaseModel):
    id: str
    variant_text: str
    selected: bool

    class Config:
        from_attributes = True


class PoemOut(BaseModel):
    id: str
    source: str
    content: Optional[str]
    status: str
    variants: List[PoemVariantOut] = []

    class Config:
        from_attributes = True


class PoemWriteRequest(BaseModel):
    user_id: str
    content: str


class PoemSelectVariantRequest(BaseModel):
    variant_id: str


class TemplateOut(BaseModel):
    id: str
    name: str
    category: str
    mood_tags: list
    preview_thumbnail_url: Optional[str]

    class Config:
        from_attributes = True


class MusicTrackOut(BaseModel):
    id: str
    title: str
    mood_tags: list
    audio_file_url: str
    duration_seconds: Optional[int]

    class Config:
        from_attributes = True


class CreationCreateRequest(BaseModel):
    user_id: str
    poem_id: str
    template_id: str
    music_track_id: str


class CreationOut(BaseModel):
    id: str
    poem_id: str
    template_id: str
    music_track_id: str
    rendered_video_url: Optional[str]
    thumbnail_url: Optional[str]
    share_link_slug: str
    status: str

    class Config:
        from_attributes = True


class ShareEventRequest(BaseModel):
    creation_id: str
    channel: str


# ---- Credits ----

class CreditPackOut(BaseModel):
    id: str
    label: str
    credits: int
    price_inr: int

    class Config:
        from_attributes = True


class CreateCheckoutOrderRequest(BaseModel):
    user_id: str
    credit_pack_id: str


class CreateCheckoutOrderResponse(BaseModel):
    transaction_id: str
    cashfree_order_id: str
    payment_session_id: str
    cashfree_env: str    # "sandbox" | "production" - passed to Cashfree's JS SDK
    amount_inr: int
    currency: str = "INR"
    credits: int


class VerifyPaymentRequest(BaseModel):
    transaction_id: str
    cashfree_order_id: str


class VerifyPaymentResponse(BaseModel):
    status: str          # "paid" | "failed"
    credits_added: int
    new_balance: int


class CreditBalanceOut(BaseModel):
    user_id: str
    credits_balance: int

    class Config:
        from_attributes = True
