"""
Run with: python seed_data.py
Populates templates and music_tracks with starter content so the
create flow is testable end-to-end. Music is three original synthesised
placeholder tracks in static/music/ (see generate.sh); replace them and the
placeholder template URLs with real Lottie/Rive files and licensed audio.
"""
from app.database import SessionLocal
from app import models

# Tables come from Alembic migrations (`alembic upgrade head`), not from this script.
db = SessionLocal()

templates = [
    dict(name="Sunset Walk", category="sunset_walk",
         mood_tags=["romantic", "nostalgic"],
         lottie_file_url="https://cdn.example.com/templates/sunset_walk.json",
         preview_thumbnail_url="https://cdn.example.com/templates/sunset_walk.jpg"),
    dict(name="Cherry Blossom", category="cherry_blossom",
         mood_tags=["romantic", "playful"],
         lottie_file_url="https://cdn.example.com/templates/cherry_blossom.json",
         preview_thumbnail_url="https://cdn.example.com/templates/cherry_blossom.jpg"),
    dict(name="Starry Night", category="starry_night",
         mood_tags=["deeply_romantic", "nostalgic"],
         lottie_file_url="https://cdn.example.com/templates/starry_night.json",
         preview_thumbnail_url="https://cdn.example.com/templates/starry_night.jpg"),
    dict(name="Cozy Rain", category="cozy_rain",
         mood_tags=["nostalgic", "cozy"],
         lottie_file_url="https://cdn.example.com/templates/cozy_rain.json",
         preview_thumbnail_url="https://cdn.example.com/templates/cozy_rain.jpg"),
]

tracks = [
    dict(title="Soft Piano Love", artist="Tweezers (synth placeholder)", license_source="placeholder_synth",
         mood_tags=["deeply_romantic"], audio_file_url="/static/music/soft_piano_love.mp3",
         duration_seconds=32),
    dict(title="Playful Strings", artist="Tweezers (synth placeholder)", license_source="placeholder_synth",
         mood_tags=["playful"], audio_file_url="/static/music/playful_strings.mp3",
         duration_seconds=32),
    dict(title="Nostalgic Guitar", artist="Tweezers (synth placeholder)", license_source="placeholder_synth",
         mood_tags=["nostalgic"], audio_file_url="/static/music/nostalgic_guitar.mp3",
         duration_seconds=32),
]

for t in templates:
    if not db.query(models.Template).filter_by(name=t["name"]).first():
        db.add(models.Template(**t))

for m in tracks:
    if not db.query(models.MusicTrack).filter_by(title=m["title"]).first():
        db.add(models.MusicTrack(**m))

# Credit packs. 1 credit = Rs 1 by convention; a story generation costs
# COST_PER_STORY_CREDITS (default 5, see app/routers/poems.py) so these
# packs map to roughly 10-40 story generations each.
credit_packs = [
    dict(label="Starter Pack", credits=50, price_inr=49),
    dict(label="Value Pack", credits=120, price_inr=99),
    dict(label="Love Bundle", credits=300, price_inr=199),
]
for p in credit_packs:
    if not db.query(models.CreditPack).filter_by(label=p["label"]).first():
        db.add(models.CreditPack(**p))

db.commit()
print(f"Seeded {len(templates)} templates, {len(tracks)} music tracks, {len(credit_packs)} credit packs.")
