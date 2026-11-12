"""
==========================================================
AI News Aggregator - REST API, Semantic Clusters & SaaS Dashboard
Author : Chaitanya Upadhyay
==========================================================
"""

import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, BackgroundTasks, Query, Response, HTTPException, status, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, PlainTextResponse
from pydantic import BaseModel, EmailStr

from app.database.repository import Repository
from app.database.connection import get_database_url, get_mongo_db
from app.daily_runner import run_daily_pipeline
from app.config import (
    GROQ_MODEL,
    RSS_FEEDS,
    YOUTUBE_CHANNELS
)
from app.services.webhook_alerts import get_webhook_service
from app.services.vector_clustering import get_clustering_service
from app.profiles.preference_manager import get_preference_manager
from app.services.demo_data import seed_demo_digests
from app.services.email import (
    send_welcome_email,
    send_digest_newsletter,
    send_review_confirmation_email,
    send_admin_review_notification,
    send_admin_unsubscribe_alert,
    MY_EMAIL,
    EMAIL_ENABLED
)
from app.services.moderation import contains_abusive_language
from app.services.email_validator import validate_email_address

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AI News Aggregator & Intelligence SaaS Engine",
    description="Automated AI news scraping, Groq LLM summarization, user authentication, and automated email distribution.",
    version="2.3.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static assets
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/favicon.ico", include_in_schema=False)
def get_favicon():
    fav_path = os.path.join(os.path.dirname(__file__), "static", "favicon.ico")
    if os.path.exists(fav_path):
        return FileResponse(fav_path, media_type="image/x-icon")
    return Response(status_code=204)


@app.on_event("startup")
def on_startup():
    from app.database.connection import init_db
    init_db()


# ---------------- In-Memory Sliding Window Rate Limiter ----------------
_rate_limits = defaultdict(list)

def enforce_rate_limit(client_ip: str, limit: int = 15, window_seconds: int = 60):
    now = time.time()
    _rate_limits[client_ip] = [t for t in _rate_limits[client_ip] if now - t < window_seconds]
    if len(_rate_limits[client_ip]) >= limit:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please wait a minute before submitting again."
        )
    _rate_limits[client_ip].append(now)


# Pydantic Schemas
class PreferencesUpdate(BaseModel):
    preferred_topics: Optional[List[str]] = None
    excluded_topics: Optional[List[str]] = None
    technical_depth_weight: Optional[float] = None
    min_relevance_score: Optional[float] = None
    slack_webhook_url: Optional[str] = None
    discord_webhook_url: Optional[str] = None


class TestAlertRequest(BaseModel):
    channel: str = "both"
    title: Optional[str] = "DeepSeek V3 Model Weights & Architecture Released"
    summary: Optional[str] = "DeepSeek announces open weights for 671B MoE reasoning model with native FP8 training support."
    url: Optional[str] = "https://arxiv.org/abs/2412.19437"
    source: Optional[str] = "arXiv AI"
    score: Optional[float] = 9.4


class SubscribeRequest(BaseModel):
    email: str
    website_hp: Optional[str] = None  # Honeypot trap for bots


class UnsubscribeRequest(BaseModel):
    email: str
    reason: Optional[str] = "User requested unsubscribe"


class ReviewCreateRequest(BaseModel):
    name: str
    email: str
    comment: str
    rating: Optional[int] = 5
    role: Optional[str] = "Community Member"
    is_public: Optional[bool] = True
    website_hp: Optional[str] = None  # Honeypot trap for bots


class SignupRequest(BaseModel):
    email: str
    password: str
    name: Optional[str] = None
    email_subscribed: bool = True


class LoginRequest(BaseModel):
    email: str
    password: str


class ToggleSubscriptionRequest(BaseModel):
    user_id: str
    subscribed: bool


class SendEmailDigestRequest(BaseModel):
    recipient_email: Optional[str] = None
    hours: int = 168
    limit: int = 10


# ---------------- Web & Static Routes ----------------
@app.get("/", response_class=HTMLResponse)
@app.get("/api", response_class=HTMLResponse)
@app.get("/api/", response_class=HTMLResponse)
@app.get("/api/index", response_class=HTMLResponse)
@app.get("/api/index.py", response_class=HTMLResponse)
def serve_dashboard():
    """Serves the modern AI intelligence landing page frontend."""
    template_path = os.path.join(os.path.dirname(__file__), "templates", "dashboard.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h2>Synapse AI - Initializing...</h2>")


# ---------------- 1-Click Newsletter Subscription ----------------
@app.post("/api/subscribe")
def subscribe(req: SubscribeRequest, background_tasks: BackgroundTasks, request: Request):
    """
    Subscribes a user directly via email to the daily AI news briefing.
    Performs strict format, domain, and DNS MX record validation.
    Stores email in MongoDB Atlas and dispatches an automated confirmation email.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    enforce_rate_limit(client_ip, limit=15, window_seconds=60)

    repo = Repository()
    email = req.email.strip().lower()

    # Honeypot defense: silently neutralize spambots
    if req.website_hp:
        return {
            "status": "success",
            "message": "Subscription received.",
            "email": email,
            "total_subscribers": repo.get_subscribers_count()
        }
    
    # Strict multi-layer email validation
    is_valid, validation_msg = validate_email_address(email)
    if not is_valid:
        print(f"[SUBSCRIBE] ⚠️ Rejected invalid email '{email}': {validation_msg}", flush=True)
        raise HTTPException(status_code=400, detail=validation_msg)

    print(f"[SUBSCRIBE] 📬 Processing verified subscription for: {email}", flush=True)
    res = repo.subscribe_email(email)
    already_subscribed = res.get("already_subscribed", False)
    reactivated = res.get("reactivated", False)
    is_created = res.get("created", False)

    if already_subscribed:
        print(f"[SUBSCRIBE] ℹ️ User '{email}' is already an active subscriber. Skipping welcome email.", flush=True)
        return {
            "status": "already_subscribed",
            "already_subscribed": True,
            "message": f"You are already a subscribed user! Your daily AI briefing is already active for {email}.",
            "email": email,
            "total_subscribers": repo.get_subscribers_count()
        }

    # Only send welcome confirmation email if it is a brand new subscription or a reactivation
    print(f"[SUBSCRIBE] 🚀 Queuing welcome confirmation email for: {email}", flush=True)
    background_tasks.add_task(send_welcome_email, email, email.split("@")[0])

    if reactivated:
        msg = f"✓ Welcome back! Your subscription has been reactivated for {email}."
    else:
        msg = f"✓ Subscribed successfully! Confirmation email dispatched to {email}."

    print(f"[SUBSCRIBE] ✅ Subscription complete for: {email} (Total subscribers: {repo.get_subscribers_count()})", flush=True)

    return {
        "status": "success",
        "already_subscribed": False,
        "message": msg,
        "email": email,
        "total_subscribers": repo.get_subscribers_count()
    }


# ---------------- 1-Click Unsubscribe ----------------
@app.post("/api/unsubscribe")
def unsubscribe(req: UnsubscribeRequest, background_tasks: BackgroundTasks):
    """
    Unsubscribes a user from the daily AI briefing.
    Marks them inactive in database and notifies the founder via SMTP.
    """
    repo = Repository()
    email = req.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Please provide a valid email address.")

    print(f"[UNSUBSCRIBE] Processing unsubscribe request for: {email}", flush=True)
    res = repo.unsubscribe_email(email, reason=req.reason)

    # Send founder alert in background
    background_tasks.add_task(send_admin_unsubscribe_alert, email, req.reason)

    return {
        "status": "success",
        "message": f"✓ {email} has been unsubscribed. You will not receive any further emails.",
        "email": email,
        "total_subscribers": repo.get_subscribers_count()
    }


@app.get("/api/unsubscribe")
def unsubscribe_link(email: Optional[str] = Query(None), background_tasks: BackgroundTasks = None):
    """
    Direct 1-click unsubscribe endpoint triggered from email footers.
    """
    repo = Repository()
    if email:
        clean_email = email.strip().lower()
        repo.unsubscribe_email(clean_email, reason="1-click link in email")
        if background_tasks:
            background_tasks.add_task(send_admin_unsubscribe_alert, clean_email, "1-click link in email")
        else:
            try:
                send_admin_unsubscribe_alert(clean_email, "1-click link in email")
            except Exception:
                pass

        html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Unsubscribed – Synapse AI</title>
  <style>
    body {{ background: #000; color: #fff; font-family: -apple-system, system-ui, sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 20px; }}
    .card {{ background: #080808; border: 1px solid #222; border-radius: 16px; padding: 40px 32px; max-width: 480px; text-align: center; }}
    h1 {{ font-size: 24px; font-weight: 800; margin-bottom: 12px; }}
    p {{ color: #888; font-size: 15px; line-height: 1.6; margin-bottom: 24px; }}
    .email-box {{ background: #111; border: 1px solid #333; padding: 10px 16px; border-radius: 8px; font-family: monospace; color: #fff; display: inline-block; margin-bottom: 24px; }}
    a.btn {{ display: inline-block; background: #fff; color: #000; font-weight: 700; text-decoration: none; padding: 12px 24px; border-radius: 999px; font-size: 14px; }}
  </style>
</head>
<body>
  <div class="card">
    <div style="font-size: 32px; margin-bottom: 12px;">✓</div>
    <h1>You're Unsubscribed</h1>
    <div class="email-box">{clean_email}</div>
    <p>You have been removed from our dispatch list. No further daily AI briefings will be sent to your inbox. You can rejoin anytime by visiting our website.</p>
    <a href="/" class="btn">Return to Synapse AI</a>
  </div>
</body>
</html>"""
        return HTMLResponse(content=html_content)

    return HTMLResponse("<h2>Please specify an email address to unsubscribe.</h2>", status_code=400)


@app.get("/api/unsubscribers")
def list_unsubscribers():
    """Returns audit log of unsubscribed users."""
    return {"status": "success", "unsubscribers": Repository().get_unsubscribers()}


# ---------------- Community Reviews & Feedback ----------------
@app.get("/api/reviews")
def get_reviews():
    """Returns community reviews and testimonials."""
    repo = Repository()
    reviews = repo.get_reviews(limit=50)
    return {"status": "success", "reviews": reviews}


@app.post("/api/reviews")
def submit_review(req: ReviewCreateRequest, background_tasks: BackgroundTasks, request: Request):
    """
    Submits a new community review to MongoDB Atlas.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    enforce_rate_limit(client_ip, limit=10, window_seconds=60)

    # Honeypot defense: silently neutralize spambots
    if req.website_hp:
        return {
            "status": "success",
            "message": "✓ Thank you! Your review has been received.",
            "is_public": False,
            "is_approved": False
        }

    name = req.name.strip()
    email = req.email.strip().lower()
    comment = req.comment.strip()
    rating = max(1, min(5, int(req.rating or 5)))
    role = (req.role or "Community Member").strip()
    is_public = bool(req.is_public)

    print(f"[REVIEW] 📝 Inbound review from: '{name}' <{email}> (Rating: {rating}★, Visibility: {'PUBLIC' if is_public else 'PRIVATE'})", flush=True)

    if not name:
        raise HTTPException(status_code=400, detail="Name is required.")
    
    is_valid, validation_msg = validate_email_address(email)
    if not is_valid:
        raise HTTPException(status_code=400, detail=validation_msg)
        
    if not comment:
        raise HTTPException(status_code=400, detail="Review comment is required.")

    # Automated safety & abusive words moderation
    is_toxic, flagged_word = contains_abusive_language(f"{name} {comment}")
    is_approved = not is_toxic

    if is_toxic:
        print(f"[MODERATION] ⚠️ Content safety violation detected: Flagged word '{flagged_word}'. Review by '{name}' marked as unapproved.", flush=True)
    else:
        print(f"[MODERATION] 🛡️ Content safety passed for review by '{name}'.", flush=True)

    repo = Repository()
    review = repo.add_review(
        name=name,
        email=email,
        comment=comment,
        rating=rating,
        role=role,
        is_public=is_public,
        is_approved=is_approved
    )
    print(f"[REVIEW] 💾 Review saved to MongoDB Atlas (ID: {review.get('id')}).", flush=True)

    # Background task 1: Automated confirmation email to reviewer
    print(f"[EMAIL] 🚀 Scheduling confirmation email to reviewer: {email}", flush=True)
    background_tasks.add_task(
        send_review_confirmation_email,
        user_email=email,
        name=name,
        rating=rating,
        comment=comment,
        is_public=is_public,
        is_approved=is_approved
    )

    # Background task 2: Instant alert to site owner (especially for private feedback or safety flags)
    print(f"[EMAIL] 🚀 Scheduling admin notification alert to founder ({MY_EMAIL})", flush=True)
    background_tasks.add_task(
        send_admin_review_notification,
        reviewer_name=name,
        reviewer_email=email,
        rating=rating,
        comment=comment,
        role=role,
        is_public=is_public,
        is_approved=is_approved
    )

    if not is_approved:
        msg = "Thank you! Your feedback has been received and queued for safety moderation."
    elif not is_public:
        msg = "✓ Thank you! Your private feedback has been delivered securely to our founders."
    else:
        msg = "✓ Thank you! Your review has been published live on Synapse AI."

    # Remove email before returning to client for privacy protection
    safe_review = {k: v for k, v in review.items() if k != "email"}

    return {
        "status": "success",
        "message": msg,
        "is_public": is_public,
        "is_approved": is_approved,
        "review": safe_review if (is_public and is_approved) else None
    }


# ---------------- Diagnostics & Telemetry Logs ----------------
@app.get("/api/logs/emails")
def get_email_logs(limit: int = 50):
    """
    Diagnostics endpoint: Returns recent email delivery logs from MongoDB Atlas.
    Allows real-time inspection of email successes, failures, and error reasons.
    """
    logs = Repository().get_email_logs(limit=limit)
    return {
        "status": "success",
        "count": len(logs),
        "smtp_configured": bool(os.getenv("APP_PASSWORD") or os.getenv("EMAIL_APP_PASSWORD")),
        "smtp_host": os.getenv("SMTP_HOST") or os.getenv("SMTP_SERVER", "smtp.gmail.com"),
        "logs": logs
    }


@app.get("/api/test-email")
@app.post("/api/test-email")
def test_email_dispatch():
    """
    Live Diagnostic: Sends a test ping email to configured MY_EMAIL.
    Immediately returns whether SMTP connected, authenticated, and delivered, or the exact failure reason.
    """
    from app.services.email import send_email, MY_EMAIL, SMTP_HOST, SMTP_PORT
    print(f"[DIAGNOSTICS] 🧪 Running test email dispatch to {MY_EMAIL}...", flush=True)
    res = send_email(
        subject="Synapse AI — SMTP Diagnostics Ping",
        body_text=f"Hello,\n\nThis is a diagnostic test email verifying that Gmail SMTP is operating properly on Vercel!\nTimestamp: {datetime.now().isoformat()}",
        recipients=[MY_EMAIL],
        email_type="diagnostic_test"
    )
    return {
        "status": "success" if res.get("success") else "error",
        "result": res,
        "sender": MY_EMAIL,
        "smtp_host": SMTP_HOST,
        "smtp_port": SMTP_PORT,
        "hint": "If failed, verify that Google App Password is 16 characters with no spaces in Vercel Environment Variables." if not res.get("success") else "SMTP is working 100%!"
    }


# ---------------- SaaS User Authentication ----------------
@app.post("/api/auth/signup")
def signup(req: SignupRequest, background_tasks: BackgroundTasks):
    """
    Registers a new SaaS user.
    Sends an automated welcome email from the configured SMTP account.
    """
    repo = Repository()
    normalized_email = req.email.lower().strip()
    if not normalized_email or "@" not in normalized_email:
        raise HTTPException(status_code=400, detail="Invalid email address.")

    if len(req.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters.")

    existing = repo.get_user_by_email(normalized_email)
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    user = repo.create_user(
        email=normalized_email,
        password=req.password,
        name=req.name,
        email_subscribed=req.email_subscribed
    )
    if not user:
        raise HTTPException(status_code=500, detail="Failed to create user account.")

    # Schedule welcome email in background task via SMTP
    background_tasks.add_task(send_welcome_email, user.email, user.name)

    return {
        "status": "success",
        "message": f"Account created! Welcome email dispatched to {user.email}.",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "email_subscribed": user.email_subscribed
        }
    }


@app.post("/api/auth/login")
def login(req: LoginRequest):
    """Authenticates existing SaaS user."""
    repo = Repository()
    user = repo.authenticate_user(req.email, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    return {
        "status": "success",
        "message": f"Welcome back, {user.name}!",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "email_subscribed": user.email_subscribed,
            "last_login": user.last_login.isoformat() if user.last_login else None
        }
    }


@app.post("/api/auth/toggle-subscription")
def toggle_subscription(req: ToggleSubscriptionRequest):
    """Updates email newsletter subscription status for a user."""
    repo = Repository()
    updated = repo.update_user_subscription(req.user_id, req.subscribed)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found.")
    return {
        "status": "success",
        "email_subscribed": req.subscribed,
        "message": "Subscription preferences updated."
    }


@app.get("/api/auth/subscribers")
def list_subscribers():
    """Lists count and subscribers."""
    subs = Repository().get_all_subscribers_admin()
    return {"count": len(subs), "subscribers": subs}


# ---------------- Email Digest Delivery ----------------
@app.post("/api/digest/send-email")
def send_email_digest(req: SendEmailDigestRequest, background_tasks: BackgroundTasks):
    """
    Sends the curated AI news digest via SMTP.
    If recipient_email is provided, sends to that email.
    Otherwise, sends to all subscribed SaaS users and admin email.
    """
    repo = Repository()
    digests = repo.get_recent_digests(hours=req.hours)
    if not digests:
        # Fallback to demo digests if empty
        seed_demo_digests(repo)
        digests = repo.get_recent_digests(hours=req.hours)

    limit = req.limit or 10
    curated_items = digests[:limit]

    recipients: List[str] = []
    if req.recipient_email:
        recipients = [req.recipient_email.strip()]
    else:
        recipients = repo.get_all_subscriber_emails()
        if MY_EMAIL and MY_EMAIL not in recipients:
            recipients.append(MY_EMAIL)

    if not recipients:
        raise HTTPException(status_code=400, detail="No recipients found for email delivery.")

    # Schedule sending in background or execute
    dispatch_res = send_digest_newsletter(recipients, curated_items)

    return {
        "status": "dispatched" if dispatch_res.get("success") else "warning",
        "recipients_count": len(recipients),
        "recipients": recipients,
        "articles_count": len(curated_items),
        "sender": "Synapse AI Intelligence Dispatcher",
        "details": dispatch_res
    }


# ---------------- System, Stats & Feeds ----------------
@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "engine": "Synapse Neural Reasoning Engine",
        "status_detail": "Autonomous Research Pipeline Active",
        "sources_monitored": len(RSS_FEEDS) + len(YOUTUBE_CHANNELS),
        "features": {
            "saas_auth": True,
            "welcome_emails": True,
            "digest_newsletter": True,
            "semantic_clustering": True,
            "pgvector_ready": True,
            "webhook_alerts": True,
            "preference_fine_tuning": True,
            "tts_reader": True
        }
    }


@app.get("/api/stats")
def get_stats():
    repo = Repository()
    try:
        digests = repo.get_recent_digests(hours=8760)
    except Exception:
        digests = []

    clustering_svc = get_clustering_service()
    clusters = clustering_svc.cluster_articles(digests)

    # Subscribers count
    try:
        subscribers_count = repo.get_subscribers_count()
    except Exception:
        subscribers_count = 0

    # Breakdown by source
    sources_count = {}
    for d in digests:
        src = d.get("article_type", "other")
        sources_count[src] = sources_count.get(src, 0) + 1

    db_url = get_database_url()
    if get_mongo_db() is not None:
        db_type = "MongoDB Atlas"
    elif db_url.startswith("postgresql"):
        db_type = "postgresql"
    else:
        db_type = "sqlite"

    return {
        "total_digests": len(digests),
        "cluster_count": len(clusters),
        "sources_count": sources_count,
        "subscribers_count": subscribers_count,
        "subscribers": subscribers_count,
        "engine": "Synapse Neural Reasoning Core",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/api/digests")
def get_recent_digests(
    hours: int = Query(default=168, ge=0, le=8760),
    source: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None)
):
    repo = Repository()
    digests = repo.get_recent_digests(hours=hours, article_type=source, search=search)
    return {
        "count": len(digests),
        "hours_window": hours,
        "digests": digests
    }


@app.get("/api/clusters")
def get_semantic_clusters(hours: int = Query(default=168, ge=0, le=8760)):
    repo = Repository()
    try:
        digests = repo.get_recent_digests(hours=hours)
    except Exception:
        digests = []

    clustering_svc = get_clustering_service()
    clusters = clustering_svc.cluster_articles(digests)
    return {
        "total_articles": len(digests),
        "cluster_count": len(clusters),
        "clusters": clusters
    }


@app.get("/api/preferences")
def get_user_preferences():
    mgr = get_preference_manager()
    return mgr.get_preferences()


@app.post("/api/preferences")
def update_user_preferences(prefs: PreferencesUpdate):
    mgr = get_preference_manager()
    updated = mgr.update_preferences(prefs.dict(exclude_unset=True))
    return {"status": "success", "preferences": updated}


@app.post("/api/alerts/test")
def trigger_test_alert(req: TestAlertRequest):
    webhook_svc = get_webhook_service()
    prefs = get_preference_manager().get_preferences()
    if prefs.get("slack_webhook_url"):
        webhook_svc.slack_url = prefs["slack_webhook_url"]
    if prefs.get("discord_webhook_url"):
        webhook_svc.discord_url = prefs["discord_webhook_url"]

    res = webhook_svc.dispatch_alert(
        title=req.title,
        summary=req.summary,
        url=req.url,
        source=req.source,
        relevance_score=req.score
    )
    return {"status": "dispatched", "results": res}


@app.post("/api/pipeline/trigger")
def trigger_pipeline(background_tasks: BackgroundTasks, hours: int = 24, top_n: int = 10):
    background_tasks.add_task(run_daily_pipeline, hours=hours, top_n=top_n)
    return {
        "status": "triggered",
        "message": f"Daily pipeline running in background for last {hours} hours (top {top_n} articles)."
    }


@app.post("/api/demo/seed")
def seed_demo_data():
    """Populates realistic AI research digests for demonstration and evaluation."""
    repo = Repository()
    inserted = seed_demo_digests(repo)
    return {
        "status": "success",
        "inserted": inserted,
        "message": f"Seeded {inserted} high-impact AI research digests."
    }


@app.post("/api/demo/clear")
def clear_demo_data():
    """Clears all digests for testing resets."""
    repo = Repository()
    from app.database.models import Digest
    count = repo.session.query(Digest).delete()
    repo.session.commit()
    return {"status": "success", "deleted": count}


@app.get("/api/export/markdown")
def export_markdown_digest():
    """Generates and downloads a clean Markdown newsletter digest."""
    repo = Repository()
    digests = repo.get_recent_digests(hours=168)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    md_lines = [
        f"# ⚡ AI Intelligence Digest — {now_str}",
        f"*Curated via Groq Llama-3.3-70B Inference & Multi-Source Scrapers*\n",
        "---\n"
    ]

    if not digests:
        md_lines.append("No digests available for this period.")
    else:
        for idx, d in enumerate(digests, start=1):
            source = (d.get("article_type") or "AI").upper()
            title = d.get("title", "Untitled")
            summary = d.get("summary", "")
            url = d.get("url", "#")
            md_lines.append(f"### {idx}. [{title}]({url})")
            md_lines.append(f"**Source:** `{source}`  ")
            md_lines.append(f"{summary}\n")

    md_content = "\n".join(md_lines)
    return Response(
        content=md_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=ai-news-digest-{now_str}.md"}
    )


# ---------------- RSS & Atom Feed Generation ----------------
@app.get("/rss", response_class=Response)
@app.get("/feed.xml", response_class=Response)
def get_rss_feed():
    """Generates standard RSS 2.0 XML feed for RSS readers (Feedly, Inoreader, etc.)."""
    repo = Repository()
    digests = repo.get_recent_digests(hours=720)
    now_rfc = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")

    items_xml = []
    for d in (digests or [])[:35]:
        title = (d.get("title") or "AI Update").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        link = (d.get("url") or "https://ai-news-aggregator-master-gic3.vercel.app").replace("&", "&amp;")
        summary = (d.get("summary") or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        source = (d.get("article_type") or "AI").upper()
        item_id = d.get("id") or str(d.get("_id", ""))

        pub_dt = d.get("created_at")
        pub_str = now_rfc
        if isinstance(pub_dt, datetime):
            pub_str = pub_dt.strftime("%a, %d %b %Y %H:%M:%S GMT")
        elif isinstance(pub_dt, str):
            try:
                dt_obj = datetime.fromisoformat(pub_dt.replace("Z", "+00:00"))
                pub_str = dt_obj.strftime("%a, %d %b %Y %H:%M:%S GMT")
            except Exception:
                pub_str = now_rfc

        items_xml.append(f"""    <item>
      <title>[{source}] {title}</title>
      <link>{link}</link>
      <guid isPermaLink="false">{item_id}</guid>
      <pubDate>{pub_str}</pubDate>
      <description>{summary}</description>
    </item>""")

    xml_content = f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Synapse AI – Daily Frontier AI Research Briefing</title>
    <link>https://ai-news-aggregator-master-gic3.vercel.app</link>
    <description>Autonomous neural synthesis of frontier AI research, open weights, and lab releases.</description>
    <language>en-us</language>
    <lastBuildDate>{now_rfc}</lastBuildDate>
    <atom:link href="https://ai-news-aggregator-master-gic3.vercel.app/rss" rel="self" type="application/rss+xml" />
{chr(10).join(items_xml)}
  </channel>
</rss>"""
    return Response(content=xml_content, media_type="application/rss+xml")


# ---------------- Search Engine Optimization (SEO) ----------------
@app.get("/robots.txt", response_class=PlainTextResponse)
def get_robots_txt():
    """Search engine crawler policy."""
    return """User-agent: *
Allow: /
Allow: /rss
Allow: /feed.xml
Disallow: /api/unsubscribers
Disallow: /api/logs/

Sitemap: https://ai-news-aggregator-master-gic3.vercel.app/sitemap.xml
"""


@app.get("/sitemap.xml", response_class=Response)
def get_sitemap_xml():
    """XML sitemap for Googlebot indexation."""
    now_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://ai-news-aggregator-master-gic3.vercel.app/</loc>
    <lastmod>{now_date}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://ai-news-aggregator-master-gic3.vercel.app/rss</loc>
    <lastmod>{now_date}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.8</priority>
  </url>
</urlset>"""
    return Response(content=sitemap, media_type="application/xml")


