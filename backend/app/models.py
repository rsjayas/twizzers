import uuid
import datetime as dt

from sqlalchemy import (
    Column, String, Text, Boolean, ForeignKey, DateTime, Integer, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .database import Base


def gen_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    phone = Column(String, unique=True, nullable=True)
    email = Column(String, unique=True, nullable=True)
    name = Column(String, nullable=True)
    auth_provider = Column(String, default="otp")
    credits_balance = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    poems = relationship("Poem", back_populates="user")
    creations = relationship("Creation", back_populates="user")
    credit_transactions = relationship("CreditTransaction", back_populates="user")


class Partner(Base):
    __tablename__ = "partners"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"))
    partner_name = Column(String)
    partner_nickname = Column(String, nullable=True)
    relationship_start_date = Column(DateTime, nullable=True)
    occasion_reminders = Column(JSON, default=dict)


class Poem(Base):
    __tablename__ = "poems"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"))
    source = Column(String)  # 'written' | 'ai_generated'
    original_prompt = Column(JSON, nullable=True)
    content = Column(Text, nullable=True)
    status = Column(String, default="draft")  # 'draft' | 'finalized'
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)

    user = relationship("User", back_populates="poems")
    variants = relationship("PoemVariant", back_populates="poem")


class PoemVariant(Base):
    __tablename__ = "poem_variants"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    poem_id = Column(UUID(as_uuid=False), ForeignKey("poems.id"))
    variant_text = Column(Text)
    selected = Column(Boolean, default=False)

    poem = relationship("Poem", back_populates="variants")


class Template(Base):
    __tablename__ = "templates"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String)
    category = Column(String)
    mood_tags = Column(JSON, default=list)
    lottie_file_url = Column(String, nullable=True)
    rive_file_url = Column(String, nullable=True)
    preview_thumbnail_url = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)


class MusicTrack(Base):
    __tablename__ = "music_tracks"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    title = Column(String)
    artist = Column(String, nullable=True)
    license_source = Column(String, nullable=True)
    mood_tags = Column(JSON, default=list)
    audio_file_url = Column(String)
    duration_seconds = Column(Integer, nullable=True)
    preview_start_ms = Column(Integer, default=0)


class Creation(Base):
    __tablename__ = "creations"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"))
    poem_id = Column(UUID(as_uuid=False), ForeignKey("poems.id"))
    template_id = Column(UUID(as_uuid=False), ForeignKey("templates.id"))
    music_track_id = Column(UUID(as_uuid=False), ForeignKey("music_tracks.id"))
    rendered_video_url = Column(String, nullable=True)
    thumbnail_url = Column(String, nullable=True)
    share_link_slug = Column(String, unique=True, default=gen_uuid)
    recipient_view_count = Column(Integer, default=0)
    status = Column(String, default="rendering")  # rendering | ready | failed
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    user = relationship("User", back_populates="creations")
    poem = relationship("Poem")
    template = relationship("Template")
    music_track = relationship("MusicTrack")


class Share(Base):
    __tablename__ = "shares"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    creation_id = Column(UUID(as_uuid=False), ForeignKey("creations.id"))
    channel = Column(String)  # instagram | whatsapp | link | download
    shared_at = Column(DateTime, default=dt.datetime.utcnow)


class CreditPack(Base):
    """
    A purchasable bundle of credits, e.g. 50 credits for Rs 49.
    Sold ONLY through the external web checkout (never inside the app),
    so this purchase is outside Google Play's in-app billing scope.
    """
    __tablename__ = "credit_packs"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    label = Column(String)                 # "Starter Pack", "Value Pack", etc.
    credits = Column(Integer, nullable=False)
    price_inr = Column(Integer, nullable=False)   # in rupees (whole number for simplicity)
    is_active = Column(Boolean, default=True)


class CreditTransaction(Base):
    """
    One attempted/completed credit purchase. Created in 'created' state when
    the web checkout page requests a Cashfree order, then moved to 'paid' or
    'failed' once Cashfree confirms the payment (via webhook or verify call).
    """
    __tablename__ = "credit_transactions"
    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"))
    credit_pack_id = Column(UUID(as_uuid=False), ForeignKey("credit_packs.id"))
    credits = Column(Integer, nullable=False)
    amount_inr = Column(Integer, nullable=False)
    cashfree_order_id = Column(String, unique=True, nullable=True)
    cashfree_payment_id = Column(String, nullable=True)
    status = Column(String, default="created")  # created | paid | failed
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    paid_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="credit_transactions")
    credit_pack = relationship("CreditPack")
