"""
Poem generation via the Anthropic API.

Requires the ANTHROPIC_API_KEY environment variable to be set.
Get a key at https://console.anthropic.com/
"""
import os
import json
import httpx

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are a romantic poet writing a short, heartfelt poem \
(6-10 lines) for someone to send their partner. Match the requested tone \
exactly. Avoid cliches where possible; use the personal details naturally, \
not forced. Never use generic filler lines.

Respond ONLY with a JSON array of exactly 3 strings, each a distinct poem \
variation. No preamble, no markdown fences, no extra keys. Example:
["poem one text...", "poem two text...", "poem three text..."]
"""


async def generate_poem_variants(
    occasion: str,
    tone: str,
    relationship_length: str | None,
    detail_1: str | None,
    detail_2: str | None,
    recipient_nickname: str | None,
) -> list[str]:
    if not ANTHROPIC_API_KEY:
        # Fallback so the app is testable without a key configured yet.
        return [
            f"[DEMO POEM 1 - set ANTHROPIC_API_KEY for real output]\n"
            f"A {tone} note for {recipient_nickname or 'you'} on this {occasion}.",
            f"[DEMO POEM 2 - set ANTHROPIC_API_KEY for real output]\n"
            f"Another take, same {tone} heart, same {occasion}.",
            f"[DEMO POEM 3 - set ANTHROPIC_API_KEY for real output]\n"
            f"A third try, still {tone}, still for {recipient_nickname or 'you'}.",
        ]

    user_content = (
        f"Occasion: {occasion}\n"
        f"Tone: {tone}\n"
        f"Relationship length: {relationship_length or 'unspecified'}\n"
        f"Personal detail 1: {detail_1 or 'none'}\n"
        f"Personal detail 2: {detail_2 or 'none'}\n"
        f"Recipient nickname: {recipient_nickname or 'unspecified'}\n"
    )

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            ANTHROPIC_URL,
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": MODEL,
                "max_tokens": 800,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_content}],
            },
        )
        resp.raise_for_status()
        data = resp.json()

    text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
    raw = "".join(text_blocks).strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        variants = json.loads(raw)
        if isinstance(variants, list) and all(isinstance(v, str) for v in variants):
            return variants[:3]
    except json.JSONDecodeError:
        pass

    # If parsing fails, return the raw text as a single variant rather than erroring out.
    return [raw]
