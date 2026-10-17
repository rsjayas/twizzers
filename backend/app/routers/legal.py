"""Public pages the app stores require: privacy policy, terms, account deletion, plus /config.

The privacy policy and terms are DRAFTS written from what the app actually does. Have a lawyer
review them, fill in the company details (LEGAL_COMPANY_NAME, LEGAL_CONTACT_EMAIL, LEGAL_UPDATED)
and keep the list of services current before publishing.
"""
import html
import os

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from .. import settings_store
from ..database import get_db

router = APIRouter(tags=["legal"])


def _vars() -> dict:
    return {
        "company": html.escape(os.getenv("LEGAL_COMPANY_NAME", "Tweezers")),
        "email": html.escape(os.getenv("LEGAL_CONTACT_EMAIL", "support@example.com")),
        "updated": html.escape(os.getenv("LEGAL_UPDATED", "17 October 2026")),
    }


def _page(title: str, body: str) -> HTMLResponse:
    v = _vars()
    draft = ('<p class="draft">Draft for review: this text describes how the app works but has not been checked '
             'by a lawyer. Replace the placeholder company name and contact address before publishing.</p>'
             if os.getenv("LEGAL_DRAFT_BANNER", "true").lower() == "true" else "")
    return HTMLResponse(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} - {v['company']}</title>
<style>
body{{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;line-height:1.6;color:#2b1a22;max-width:720px;margin:0 auto;padding:24px 16px 64px}}
h1{{font-size:1.6rem}} h2{{font-size:1.1rem;margin-top:1.8em}} a{{color:#d1416b}}
.draft{{background:#fff3cd;border:1px solid #f0d9a6;padding:10px 14px;border-radius:8px;font-size:.9rem}}
.muted{{color:#7d6471;font-size:.9rem}}
</style></head><body>
<h1>{html.escape(title)}</h1>
<p class="muted">{v['company']} &middot; last updated {v['updated']}</p>
{draft}
{body.format(**v)}
</body></html>""")


@router.get("/privacy", response_class=HTMLResponse)
def privacy():
    return _page("Privacy policy", """
<p>{company} ("we") makes an app for writing poems and turning them into short videos to share with people you care about.
This page explains what information we handle and why. Contact: <a href="mailto:{email}">{email}</a>.</p>

<h2>What we collect</h2>
<ul>
<li><b>Your account:</b> your email address and name, or your phone number if you sign in with it, and which sign-in method you used (email and password, Google, or phone). Passwords are handled by Google Firebase; we never see or store them.</li>
<li><b>What you create:</b> poems you write or generate, the style and music you choose, the videos made from them, and when you share them.</li>
<li><b>AI poems:</b> when you ask for an AI poem, the details you type (occasion, tone, a name or nickname, short memories) are sent to Anthropic's Claude service to write the poem.</li>
<li><b>Payments:</b> if you buy credits, we keep the amount, the credits and the payment reference. Card, UPI and bank details are handled by our payment provider (Cashfree) and are not seen by us.</li>
<li><b>Reports:</b> if you report a video from its public page, we keep your reason, your note, and a scrambled (hashed) form of your IP address so we can limit abuse.</li>
<li><b>Technical data:</b> basic server logs such as time, requested address and errors.</li>
</ul>

<h2>Who else handles your information</h2>
<p>We use these services to run the app: Google Firebase (sign-in), Anthropic (AI poems), Neon (database), Cloudflare (storing and delivering videos), Cashfree (payments), and our hosting provider. They process data for us and are not allowed to use it for their own purposes beyond running their service. We do not sell your information.</p>

<h2>Videos you share</h2>
<p>Anyone who has the link to a video can watch it and read the poem, without signing in. Share the link only with people you want to see it. You can ask us to remove a video, and viewers can report one to us.</p>

<h2>How long we keep it</h2>
<p>We keep your information while your account exists. You can delete your account in the app (My account, then Delete my account) or by writing to us. Deleting removes your poems, videos, shares and sign-in details and blanks your profile. Records of payments are kept for accounting and legal reasons but no longer identify you.</p>

<h2>Your choices</h2>
<p>You can ask to see, correct or delete your information at any time at <a href="mailto:{email}">{email}</a>. You can also block marketing messages; we do not send any today.</p>

<h2>Children</h2>
<p>The app is not meant for children under 18. If you believe a child has an account, write to us and we will delete it.</p>

<h2>Security</h2>
<p>Data travels over encrypted connections, access to our admin tools needs a password and can need a second code, and changes made by staff are logged. No system is perfectly secure, so please use a strong, unique password.</p>

<h2>Changes</h2>
<p>If we change this policy in a way that matters, we will tell you in the app or by email before it applies.</p>
""")


@router.get("/terms", response_class=HTMLResponse)
def terms():
    return _page("Terms of use", """
<p>By using the app you agree to these terms. If you do not agree, please do not use it. Contact: <a href="mailto:{email}">{email}</a>.</p>

<h2>Using the app</h2>
<p>You must be 18 or older. You are responsible for your account and for what you create and share.</p>

<h2>What is not allowed</h2>
<p>Do not use the app to harass, threaten or shame anyone, to post sexual content involving minors or anything illegal, to impersonate another person, to send spam, or to put someone's private information in a poem without their agreement. We may remove content, block accounts or refuse service if these rules are broken.</p>

<h2>Your content</h2>
<p>You keep ownership of your poems. You allow us to store, process and show them (including as videos on pages that anyone with the link can open) so that the app works. AI-written poems are generated for you; check them before you share them.</p>

<h2>Credits and payments</h2>
<p>Some features may cost credits. Credits are bought on our payment page, are used to generate poems, and are not exchangeable for money except where the law requires a refund. Prices can change; credits you have already bought keep their value.</p>

<h2>Reports and removals</h2>
<p>Anyone can report a shared video. We review reports and may remove a video without notice if it breaks these terms.</p>

<h2>Service and liability</h2>
<p>We work to keep the app available but cannot promise it will always work or that videos will always be kept. To the extent the law allows, we are not liable for indirect losses, and our total liability is limited to the amount you paid us in the last 12 months.</p>

<h2>Ending your account</h2>
<p>You can delete your account in the app at any time. We may close accounts that break these terms.</p>

<h2>Changes and law</h2>
<p>We may update these terms and will tell you about important changes. These terms are governed by the laws of India, and the courts of your city of residence or ours may hear disputes (to be confirmed by your lawyer).</p>
""")


@router.get("/delete-account", response_class=HTMLResponse)
def delete_account():
    return _page("Delete your account", """
<p>You can delete your account and data at any time.</p>

<h2>In the app</h2>
<p>Open the app, go to <b>My account</b>, choose <b>Delete my account</b> and type DELETE to confirm. This takes effect immediately.</p>

<h2>Cannot use the app?</h2>
<p>Email <a href="mailto:{email}">{email}</a> from the address on your account, or tell us the email or phone number you signed up with. We will confirm it is you and delete the account, normally within 30 days.</p>

<h2>What is deleted</h2>
<ul>
<li>Your poems, videos and sharing history, and the public links to your videos stop working.</li>
<li>Your sign-in details, name, email address and phone number.</li>
</ul>
<h2>What we keep</h2>
<ul>
<li>Records of payments, as needed for accounting and the law. They no longer identify you.</li>
</ul>
""")


@router.get("/config")
def public_config(db: Session = Depends(get_db)):
    """What the app needs to know before sign-in: is charging on, what a poem costs, are sign-ups open."""
    return {
        "payments_enabled": settings_store.get_value(db, "payments_enabled"),
        "cost_per_story_credits": settings_store.get_value(db, "cost_per_story_credits"),
        "signups_enabled": settings_store.get_value(db, "signups_enabled"),
    }
