"""
==========================================================
AI News Aggregator - SaaS Email Service & Newsletter Engine
Sends Welcome Emails, Login Alerts, and AI News Digests
Powered by Gmail SMTP
Author: Chaitanya Upadhyay
==========================================================
"""

import os
import sys
import smtplib
import logging
from typing import List, Dict, Any, Optional, Tuple
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv
import markdown

load_dotenv()
logger = logging.getLogger("email_service")

# Configure root logger to output to stdout with formatted timestamps
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [EMAIL_SERVICE] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

MY_EMAIL = os.getenv("MY_EMAIL", "coderchaitanyaupadhyay@gmail.com")
if MY_EMAIL and "coderchaitanyaupadhyay.com" in MY_EMAIL and "@" not in MY_EMAIL:
    MY_EMAIL = "coderchaitanyaupadhyay@gmail.com"
RAW_PASSWORD = os.getenv("APP_PASSWORD") or os.getenv("EMAIL_APP_PASSWORD", "nczm expm gjzm uyrw")
# Normalize app password (strip any spaces)
APP_PASSWORD = RAW_PASSWORD.replace(" ", "").strip() if RAW_PASSWORD else ""
SMTP_HOST = os.getenv("SMTP_HOST") or os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "true").lower() in ("true", "1", "yes")


def log_email_msg(msg: str, is_error: bool = False):
    """Prints immediately to sys.stdout for real-time Vercel runtime logs visibility."""
    prefix = "[EMAIL_SERVICE] ❌" if is_error else "[EMAIL_SERVICE] ℹ️"
    print(f"{prefix} {msg}", flush=True)
    if is_error:
        logger.error(msg)
    else:
        logger.info(msg)


def log_to_database(recipient: str, subject: str, email_type: str, success: bool, error: Optional[str] = None):
    """Safely logs email delivery status to MongoDB Atlas."""
    try:
        from app.database.repository import Repository
        Repository().log_email_dispatch(recipient=recipient, subject=subject, email_type=email_type, success=success, error=error)
    except Exception as err:
        log_email_msg(f"Could not record email log in MongoDB: {err}", is_error=True)


def send_email(subject: str, body_text: str, body_html: Optional[str] = None, recipients: Optional[List[str]] = None, email_type: str = "general") -> Dict[str, Any]:
    """
    Dispatches personalized emails individually via Gmail SMTP with dual-port fallback (465 SSL -> 587 STARTTLS).
    Ensures COMPLETE PRIVACY: Each recipient receives an individual email where only their address appears in 'To:'.
    Includes tailored RFC 8058 1-click unsubscribe links and headers for each recipient.
    """
    sender_email = MY_EMAIL if (MY_EMAIL and "@" in MY_EMAIL) else "coderchaitanyaupadhyay@gmail.com"
    auth_user = os.getenv("SMTP_USER") or os.getenv("GMAIL_USER") or sender_email
    if auth_user and "coderchaitanyaupadhyay.com" in auth_user and "@" not in auth_user:
        auth_user = "coderchaitanyaupadhyay@gmail.com"
    if "@" not in auth_user or ("gmail.com" in SMTP_HOST and "@gmail.com" not in auth_user):
        auth_user = "coderchaitanyaupadhyay@gmail.com"
    app_pwd = APP_PASSWORD

    if not EMAIL_ENABLED:
        msg = f"EMAIL_ENABLED is set to false in environment. Skipping email dispatch of '{subject}'."
        log_email_msg(msg)
        return {"success": False, "error": msg, "recipients": []}

    if not app_pwd:
        msg = "SMTP APP_PASSWORD is missing in environment variables! Please add APP_PASSWORD in Vercel project settings."
        log_email_msg(msg, is_error=True)
        return {"success": False, "error": msg, "recipients": []}

    if recipients is None:
        recipients = [auth_user]

    valid_recipients = [r.strip() for r in recipients if r and r.strip() and "@" in r]
    if not valid_recipients:
        msg = "No valid recipient email address provided."
        log_email_msg(msg, is_error=True)
        return {"success": False, "error": msg, "recipients": []}

    log_email_msg(f"📤 Preparing individual dispatches of '{subject}' to {len(valid_recipients)} subscribers (Auth: {auth_user}, Host: {SMTP_HOST})...")

    def _build_individual_msg(rcpt: str) -> MIMEMultipart:
        m = MIMEMultipart("alternative")
        m["Subject"] = subject
        m["From"] = f"Synapse AI <{auth_user}>"
        m["To"] = rcpt

        unsub_link = f"https://ai-news-aggregator-master-gic3.vercel.app/api/unsubscribe?email={rcpt}"
        m["Precedence"] = "bulk"
        m["List-Unsubscribe"] = f"<{unsub_link}>, <mailto:{auth_user}?subject=unsubscribe>"
        m["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

        # Personalize text and html with recipient-specific unsubscribe link
        rcpt_name = rcpt.split('@')[0]
        p_text = body_text.replace("{{UNSUBSCRIBE_URL}}", unsub_link).replace("{{RECIPIENT_EMAIL}}", rcpt).replace("{{RECIPIENT_NAME}}", rcpt_name)
        m.attach(MIMEText(p_text, "plain"))

        if body_html:
            p_html = body_html.replace("{{UNSUBSCRIBE_URL}}", unsub_link).replace("{{RECIPIENT_EMAIL}}", rcpt).replace("{{RECIPIENT_NAME}}", rcpt_name)
            m.attach(MIMEText(p_html, "html"))

        return m

    def _dispatch_batch(server) -> Tuple[List[str], List[str]]:
        sent, failed = [], []
        for rcpt in valid_recipients:
            try:
                single_msg = _build_individual_msg(rcpt)
                server.sendmail(auth_user, [rcpt], single_msg.as_string())
                sent.append(rcpt)
                log_to_database(recipient=rcpt, subject=subject, email_type=email_type, success=True)
            except Exception as send_err:
                failed.append(rcpt)
                log_email_msg(f"Failed to send to {rcpt}: {send_err}", is_error=True)
                log_to_database(recipient=rcpt, subject=subject, email_type=email_type, success=False, error=str(send_err))
        return sent, failed

    errors = []
    # 1. Try SSL port 465
    try:
        log_email_msg(f"Attempting Port 465 SSL connection to {SMTP_HOST}...")
        with smtplib.SMTP_SSL(SMTP_HOST, 465, timeout=20) as server:
            server.login(auth_user, app_pwd)
            sent, failed = _dispatch_batch(server)
            log_email_msg(f"✅ SUCCESS: Delivered individual emails to {len(sent)}/{len(valid_recipients)} subscribers via Port 465 SSL!")
            return {"success": len(sent) > 0, "error": None if not failed else f"Failed for {len(failed)} recipients", "recipients": sent}
    except Exception as e465:
        err_msg = f"Port 465 SSL handshake/login failed: {e465}"
        log_email_msg(err_msg, is_error=True)
        errors.append(err_msg)

    # 2. Try STARTTLS port 587 fallback
    try:
        log_email_msg(f"Attempting Port 587 STARTTLS fallback connection to {SMTP_HOST}...")
        with smtplib.SMTP(SMTP_HOST, 587, timeout=20) as server:
            server.starttls()
            server.login(auth_user, app_pwd)
            sent, failed = _dispatch_batch(server)
            log_email_msg(f"✅ SUCCESS: Delivered individual emails to {len(sent)}/{len(valid_recipients)} subscribers via Port 587 STARTTLS!")
            return {"success": len(sent) > 0, "error": None if not failed else f"Failed for {len(failed)} recipients", "recipients": sent}
    except Exception as e587:
        err_msg = f"Port 587 STARTTLS failed: {e587}"
        log_email_msg(err_msg, is_error=True)
        errors.append(err_msg)

    err_summary = "; ".join(errors)
    log_email_msg(f"❌ CRITICAL FAILURE: Could not deliver email '{subject}'. Details: {err_summary}", is_error=True)
    return {"success": False, "error": err_summary, "recipients": []}


def send_welcome_email(user_email: str, user_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Sends an instant confirmation email when a user subscribes.
    Confirms subscription and informs them that daily AI briefings will arrive every morning at 8:00 AM.
    """
    subject = "Confirmed: You're subscribed to Synapse AI Daily Briefing"

    body_text = f"""Hello,

Your subscription to Synapse AI has been confirmed!

You will now receive our curated daily AI research briefing directly in your inbox every morning at 8:00 AM.

What you will receive:
• Autonomous synthesis of daily arXiv CS.AI papers, model weights, and benchmark results
• Direct disclosures from leading AI laboratories (OpenAI, Anthropic, Hugging Face, DeepSeek)
• A clean, zero-hype 2-minute executive read before your morning starts

No passwords or logins needed. If you ever wish to unsubscribe, you can do so in 1 click at the bottom of any briefing.

Best regards,
The Synapse AI Team
"""

    body_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Archivo", sans-serif;
      background-color: #000000;
      color: #ffffff;
      margin: 0;
      padding: 36px 16px;
      -webkit-font-smoothing: antialiased;
    }}
    .email-card {{
      max-width: 580px;
      margin: 0 auto;
      background: #050505;
      border: 1px solid #222222;
      border-radius: 14px;
      padding: 38px 32px;
      box-sizing: border-box;
    }}
    .brand {{
      display: inline-block;
      font-weight: 800;
      font-size: 20px;
      letter-spacing: -0.02em;
      color: #ffffff;
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid #222222;
      width: 100%;
    }}
    .brand span {{
      color: #8a8a8a;
      font-weight: 300;
    }}
    h1 {{
      font-size: 24px;
      font-weight: 800;
      color: #ffffff;
      letter-spacing: -0.03em;
      line-height: 1.25;
      margin: 0 0 16px;
    }}
    p {{
      color: #b5b5b5;
      font-size: 15px;
      line-height: 1.65;
      margin: 12px 0;
    }}
    .status-badge {{
      display: inline-block;
      background: #141414;
      border: 1px solid #333333;
      color: #ffffff;
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      padding: 6px 14px;
      border-radius: 999px;
      margin-bottom: 22px;
    }}
    .box {{
      background: #0c0c0c;
      border: 1px solid #222222;
      border-radius: 8px;
      padding: 22px 24px;
      margin: 26px 0;
    }}
    .box-title {{
      font-size: 12px;
      font-weight: 800;
      color: #ffffff;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 14px;
    }}
    .item {{
      color: #b5b5b5;
      font-size: 14px;
      line-height: 1.6;
      margin-bottom: 12px;
    }}
    .item strong {{
      color: #ffffff;
      font-weight: 700;
    }}
    .item a {{
      color: #ffffff;
      text-decoration: underline;
    }}
    .footer {{
      margin-top: 32px;
      padding-top: 20px;
      border-top: 1px solid #222222;
      font-size: 12px;
      color: #666666;
      line-height: 1.6;
    }}
  </style>
</head>
<body>
  <div class="email-card">
    <div class="brand">SYNAPSE<span>.AI</span></div>
    <div class="status-badge">✓ SUBSCRIPTION CONFIRMED</div>
    <h1>You're in! Your daily AI briefing is active.</h1>
    <p>
      Starting tomorrow morning, you will receive our 2-minute executive brief covering the most critical breakthroughs across frontier AI research, open weights, and lab announcements.
    </p>

    <div class="box">
      <div class="box-title">What to expect in your inbox</div>
      <div class="item">
        ✦ <strong>8:00 AM Delivery:</strong> Exactly one high-density briefing per day before your morning meetings.
      </div>
      <div class="item">
        ✦ <strong>Primary Sources:</strong> arXiv <a href="https://arxiv.org/list/cs.AI/recent">CS.AI</a> preprints, OpenAI, Anthropic, Hugging Face, and video keynotes.
      </div>
      <div class="item">
        ✦ <strong>Zero Hype:</strong> Concise architectural novelties, verified benchmark scores, and direct paper links.
      </div>
    </div>

    <p>
      No passwords or dashboard logins required. If you ever wish to cancel, you can <a href="https://ai-news-aggregator-master-gic3.vercel.app/api/unsubscribe?email={user_email}" style="color:#ffffff;text-decoration:underline;">unsubscribe anytime in 1 click</a>.
    </p>

    <div class="footer">
      Synapse AI · Autonomous Research Intelligence<br>
      This confirmation was sent to {user_email}. &nbsp;·&nbsp; <a href="https://ai-news-aggregator-master-gic3.vercel.app/api/unsubscribe?email={user_email}" style="color:#666666;text-decoration:underline;">Unsubscribe</a>
    </div>
  </div>
</body>
</html>
"""
    return send_email(subject, body_text, body_html, [user_email], email_type="welcome_email")


def send_digest_newsletter(recipients: List[str], digests: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Dispatches the latest AI news digest newsletter to users."""
    if not digests:
        return {"success": False, "error": "No digests to send"}

    now_str = datetime.now().strftime("%B %d, %Y")
    subject = f"⚡ AI Intelligence Digest — {now_str} (Top {len(digests)} Articles)"

    # Text version
    lines = [f"⚡ AI Intelligence Digest — {now_str}", ""]
    for idx, d in enumerate(digests, 1):
        lines.append(f"{idx}. {d.get('title', 'Untitled')}")
        lines.append(f"Source: {d.get('article_type', 'AI').upper()}")
        lines.append(f"Summary: {d.get('summary', '')}")
        lines.append(f"Read more: {d.get('url', '#')}")
        lines.append("-" * 30)
    body_text = "\n".join(lines)

    # HTML cards
    cards_html = ""
    for d in digests:
        src = (d.get("article_type") or "AI").upper()
        title = d.get("title", "Untitled")
        summary = d.get("summary", "")
        url = d.get("url", "#")
        cards_html += f"""
        <div style="background:#080808; border:1px solid #222222; border-radius:6px; padding:22px; margin-bottom:16px;">
          <span style="background:#1a1a1a; border:1px solid #333333; color:#ffffff; font-size:10.5px; font-weight:800; padding:3px 9px; border-radius:3px; text-transform:uppercase; letter-spacing:0.06em;">{src}</span>
          <h3 style="color:#ffffff; margin:12px 0 8px 0; font-size:18px; font-weight:800; line-height:1.35; letter-spacing:-0.02em;">{title}</h3>
          <p style="color:#b5b5b5; font-size:14px; font-weight:500; line-height:1.65; margin:0 0 14px 0;">{summary}</p>
          <a href="{url}" style="color:#ffffff; font-size:12.5px; font-weight:800; text-transform:uppercase; letter-spacing:0.05em; text-decoration:underline;">Read Source Document →</a>
        </div>
        """

    body_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background-color: #000000;
      color: #ffffff;
      margin: 0;
      padding: 30px 15px;
    }}
    .container {{
      max-width: 640px;
      margin: 0 auto;
      background: #0d0d0d;
      border: 1px solid #222222;
      border-radius: 8px;
      padding: 32px 24px;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div style="border-bottom:1px solid #222222; padding-bottom:18px; margin-bottom:24px;">
      <h1 style="color:#ffffff; font-size:24px; font-weight:900; letter-spacing:-0.03em; text-transform:uppercase; margin:0;">⚡ AI Intelligence Digest</h1>
      <p style="color:#888888; font-size:13px; font-weight:700; text-transform:uppercase; letter-spacing:0.05em; margin:6px 0 0 0;">{now_str} • Groq Llama-3.3-70B Curation</p>
    </div>

    {cards_html}

    <div style="margin-top:28px; padding-top:18px; border-top:1px solid #222222; font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.06em; color:#666666; text-align:center; line-height:1.7;">
      Transmitted to subscribed members by AI Intelligence Hub<br>
      SMTP Dispatcher: {MY_EMAIL} &nbsp;·&nbsp; <a href="https://ai-news-aggregator-master-gic3.vercel.app/api/unsubscribe" style="color:#888888;text-decoration:underline;">Unsubscribe</a>
    </div>
  </div>
</body>
</html>
"""
    return send_email(subject, body_text, body_html, recipients, email_type="daily_digest")


def markdown_to_html(markdown_text: str) -> str:
    """Converts raw markdown text to email-ready HTML."""
    body_html = markdown.markdown(markdown_text, extensions=['extra', 'nl2br'])
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      line-height: 1.6;
      color: #333;
      max-width: 600px;
      margin: 0 auto;
      padding: 20px;
    }}
  </style>
</head>
<body>
{body_html}
</body>
</html>"""


def get_source_badge(source_type: str) -> str:
    """Returns styled HTML badge for article source."""
    st = (source_type or "").lower()
    if "arxiv" in st:
        return '<span style="display:inline-block; background:#2e1065; color:#c084fc; border:1px solid #581c87; font-size:11px; font-weight:700; padding:3px 10px; border-radius:999px; letter-spacing:0.04em;">arXiv CS.AI</span>'
    elif "openai" in st:
        return '<span style="display:inline-block; background:#064e3b; color:#34d399; border:1px solid #047857; font-size:11px; font-weight:700; padding:3px 10px; border-radius:999px; letter-spacing:0.04em;">OpenAI Lab</span>'
    elif "anthropic" in st:
        return '<span style="display:inline-block; background:#431407; color:#fb923c; border:1px solid #7c2d12; font-size:11px; font-weight:700; padding:3px 10px; border-radius:999px; letter-spacing:0.04em;">Anthropic</span>'
    elif "hugging" in st:
        return '<span style="display:inline-block; background:#422006; color:#facc15; border:1px solid #713f12; font-size:11px; font-weight:700; padding:3px 10px; border-radius:999px; letter-spacing:0.04em;">Hugging Face</span>'
    elif "techcrunch" in st:
        return '<span style="display:inline-block; background:#082f49; color:#38bdf8; border:1px solid #0369a1; font-size:11px; font-weight:700; padding:3px 10px; border-radius:999px; letter-spacing:0.04em;">TechCrunch AI</span>'
    elif "youtube" in st:
        return '<span style="display:inline-block; background:#450a0a; color:#f87171; border:1px solid #7f1d1d; font-size:11px; font-weight:700; padding:3px 10px; border-radius:999px; letter-spacing:0.04em;">YouTube AI</span>'
    return '<span style="display:inline-block; background:#1f2937; color:#9ca3af; border:1px solid #374151; font-size:11px; font-weight:700; padding:3px 10px; border-radius:999px; letter-spacing:0.04em;">Frontier AI</span>'


def digest_to_html(digest_response) -> str:
    """
    Converts EmailDigestResponse object into an executive, modern dark-themed HTML newsletter.
    Designed to render beautifully on mobile & desktop mail clients (Gmail, Apple Mail, Outlook).
    """
    import html as py_html
    from app.agent.email_agent import EmailDigestResponse
    
    if not isinstance(digest_response, EmailDigestResponse):
        return markdown_to_html(digest_response.to_markdown() if hasattr(digest_response, 'to_markdown') else str(digest_response))
    
    current_date = datetime.now().strftime('%B %d, %Y')
    
    # Clean greeting & introduction (strip any legacy "Hey Dave" formatting)
    greeting_raw = digest_response.introduction.greeting or f"Daily Frontier AI Briefing · {current_date}"
    if "dave" in greeting_raw.lower():
        greeting_raw = f"Good morning! Here is your daily frontier AI briefing for {current_date}."
    
    intro_raw = digest_response.introduction.introduction or "Here are today's top curated AI breakthroughs, model releases, and research developments, analyzed and ranked for technical impact."
    
    greeting_html = markdown.markdown(greeting_raw, extensions=['extra', 'nl2br']).replace("<p>", "").replace("</p>", "").strip()
    intro_html = markdown.markdown(intro_raw, extensions=['extra', 'nl2br']).strip()
    
    cards_html = []
    for idx, article in enumerate(digest_response.articles, 1):
        safe_title = py_html.escape(article.title if hasattr(article, 'title') else article.get('title', ''))
        raw_summary = article.summary if hasattr(article, 'summary') else article.get('summary', '')
        summary_html = markdown.markdown(raw_summary, extensions=['extra', 'nl2br']).strip()
        url = article.url if hasattr(article, 'url') else article.get('url', '#')
        safe_url = py_html.escape(url)
        art_type = article.article_type if hasattr(article, 'article_type') else article.get('article_type', 'general')
        score = article.relevance_score if hasattr(article, 'relevance_score') else article.get('relevance_score', 8.5)
        
        source_badge = get_source_badge(art_type)
        
        card = f"""
        <!-- Article Card #{idx} -->
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0d0d0d; border:1px solid #222222; border-radius:12px; margin-bottom:20px; border-collapse:separate;">
          <tr>
            <td style="padding:22px 24px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:12px;">
                <tr>
                  <td align="left">{source_badge}</td>
                  <td align="right" style="color:#737373; font-size:11.5px; font-weight:700; letter-spacing:0.04em; text-transform:uppercase;">
                    #{idx} · {score:.1f}/10 Relevance
                  </td>
                </tr>
              </table>
              <h2 style="font-size:17.5px; font-weight:800; color:#ffffff; line-height:1.35; margin:0 0 12px 0; letter-spacing:-0.02em;">
                <a href="{safe_url}" target="_blank" style="color:#ffffff; text-decoration:none;">{safe_title}</a>
              </h2>
              <div style="color:#cccccc; font-size:14.5px; line-height:1.65; margin:0 0 16px 0;">
                {summary_html}
              </div>
              <div>
                <a href="{safe_url}" target="_blank" style="display:inline-block; background:#ffffff; color:#000000; text-decoration:none; font-weight:700; font-size:12.5px; padding:8px 18px; border-radius:999px;">
                  Read Full Paper &amp; Disclosures &rarr;
                </a>
              </div>
            </td>
          </tr>
        </table>
        """
        cards_html.append(card)
    
    articles_joined = "\n".join(cards_html)
    articles_count = len(digest_response.articles)
    
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Synapse AI Daily Briefing</title>
  <!--[if mso]>
  <style type="text/css">
    body, table, td {{font-family: Arial, sans-serif !important;}}
  </style>
  <![endif]-->
</head>
<body style="background-color:#000000; color:#ffffff; margin:0; padding:24px 12px; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing:antialiased;">
  <center>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:620px; margin:0 auto; background:#050505; border:1px solid #1f1f1f; border-radius:14px; overflow:hidden; border-collapse:separate;">
      
      <!-- Top Brand Header -->
      <tr>
        <td style="padding:32px 28px 20px 28px; border-bottom:1px solid #1a1a1a;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td align="left">
                <span style="font-size:20px; font-weight:900; letter-spacing:-0.03em; color:#ffffff;">SYNAPSE<span style="color:#555555; font-weight:300;">.AI</span></span>
                <div style="font-size:11.5px; font-weight:600; color:#888888; letter-spacing:0.06em; text-transform:uppercase; margin-top:4px;">
                  Autonomous Frontier AI Intelligence
                </div>
              </td>
              <td align="right" valign="top">
                <span style="display:inline-block; background:#141414; border:1px solid #282828; color:#999999; font-size:11px; font-weight:700; padding:5px 12px; border-radius:999px;">
                  {current_date}
                </span>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- Executive Overview Box -->
      <tr>
        <td style="padding:24px 28px 20px 28px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0f0f0f; border:1px solid #222222; border-radius:10px; margin-bottom:8px;">
            <tr>
              <td style="padding:18px 20px;">
                <div style="color:#10b981; font-size:11px; font-weight:800; letter-spacing:0.08em; text-transform:uppercase; margin-bottom:8px;">
                  &#9889; EXECUTIVE BRIEFING &middot; {articles_count} DISCLOSURES
                </div>
                <div style="font-size:16px; font-weight:700; color:#ffffff; line-height:1.4; margin-bottom:8px;">
                  {greeting_html}
                </div>
                <div style="color:#a3a3a3; font-size:14px; line-height:1.6;">
                  {intro_html}
                </div>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- Articles Section -->
      <tr>
        <td style="padding:4px 28px 24px 28px;">
          {articles_joined}
        </td>
      </tr>

      <!-- Branded Footer -->
      <tr>
        <td style="padding:28px; background:#030303; border-top:1px solid #1a1a1a; text-align:center;">
          <p style="color:#777777; font-size:12px; font-weight:600; line-height:1.6; margin:0 0 6px 0;">
            SYNAPSE.AI &middot; Autonomous AI Research &amp; Intelligence Engine
          </p>
          <p style="color:#555555; font-size:11.5px; line-height:1.6; margin:0 0 14px 0;">
            Delivered every morning at 8:00 AM IST &middot; Zero fluff &middot; Pure signal
          </p>
          <p style="margin:0;">
            <a href="https://ai-news-aggregator-master-gic3.vercel.app/rss" target="_blank" style="color:#888888; text-decoration:underline; font-size:12px; margin-right:16px;">
              RSS XML Feed
            </a>
            <a href="{{UNSUBSCRIBE_URL}}" target="_blank" style="color:#888888; text-decoration:underline; font-size:12px;">
              1-Click Unsubscribe
            </a>
          </p>
        </td>
      </tr>

    </table>
  </center>
</body>
</html>"""


def send_email_to_self(subject: str, body: str):
    """Sends email to configured MY_EMAIL."""
    if not MY_EMAIL:
        raise ValueError("MY_EMAIL environment variable is not set. Please set it in your .env file.")
    return send_email(subject, body, recipients=[MY_EMAIL])


def send_review_confirmation_email(
    user_email: str,
    name: str,
    rating: int,
    comment: str,
    is_public: bool = True,
    is_approved: bool = True
) -> Dict[str, Any]:
    """
    Sends an automated confirmation email to the reviewer confirming receipt of their review/feedback.
    Distinguishes whether the review was published publicly, sent privately to the founders, or held for moderation.
    """
    stars = "★" * max(1, min(5, int(rating))) + "☆" * (5 - max(1, min(5, int(rating))))
    safe_name = name.strip() if name else "Reader"

    if not is_approved:
        subject = "Synapse AI: Review Submission Received"
        status_title = "Review Under Moderation"
        status_msg = "Thank you for taking the time to share your review. Your submission has been received and flagged for safety moderation. Our team will review it shortly."
        badge_text = "STATUS: QUEUED FOR MODERATION"
        badge_color = "#f59e0b"
    elif not is_public:
        subject = "We received your private feedback - Synapse AI"
        status_title = "Private Feedback Delivered"
        status_msg = "Thank you for sharing your thoughts! Because you chose <strong>Private Feedback</strong>, your note has been forwarded directly to our founders and engineering team. It will <strong>NOT</strong> be displayed publicly on our website."
        badge_text = "VISIBILITY: PRIVATE (FOUNDER-ONLY)"
        badge_color = "#3b82f6"
    else:
        subject = f"Your review is live on Synapse AI ({stars})"
        status_title = "Your Review is Live!"
        status_msg = "Thank you for contributing to the Synapse AI community! Your review has been verified and published on our website."
        badge_text = "VISIBILITY: PUBLIC (COMMUNITY SHOWCASE)"
        badge_color = "#10b981"

    body_text = f"""Hello {safe_name},

{status_title}

{status_msg.replace('<strong>', '').replace('</strong>', '')}

Your Submitted Rating: {stars} ({rating}/5)
Your Feedback:
"{comment.strip()}"

Thank you for helping us make Synapse AI better every day.

Best regards,
The Synapse AI Team
"""

    body_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      background-color: #000000;
      color: #b5b5b5;
      margin: 0;
      padding: 36px 16px;
      -webkit-font-smoothing: antialiased;
    }}
    .box {{
      max-width: 560px;
      margin: 0 auto;
      background-color: #050505;
      border: 1px solid #222222;
      border-radius: 12px;
      padding: 38px 32px;
    }}
    .brand {{
      font-size: 19px;
      font-weight: 800;
      letter-spacing: -0.02em;
      color: #ffffff;
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid #222222;
    }}
    .badge {{
      display: inline-block;
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      padding: 5px 12px;
      border-radius: 999px;
      color: #ffffff;
      background: #141414;
      border: 1px solid #333333;
      margin-bottom: 18px;
    }}
    h1 {{
      font-size: 22px;
      font-weight: 800;
      letter-spacing: -0.03em;
      color: #ffffff;
      margin: 0 0 14px 0;
    }}
    p {{
      font-size: 14.5px;
      line-height: 1.65;
      color: #b5b5b5;
      margin: 0 0 16px 0;
    }}
    .quote-box {{
      background: #0c0c0c;
      border-left: 2px solid #ffffff;
      border: 1px solid #222222;
      border-left-width: 3px;
      padding: 16px 18px;
      margin: 22px 0;
      border-radius: 6px;
    }}
    .stars {{
      color: #ffffff;
      font-size: 15px;
      letter-spacing: 2px;
      margin-bottom: 6px;
    }}
    .quote-text {{
      font-size: 13.5px;
      color: #d4d4d4;
      line-height: 1.55;
      font-style: italic;
    }}
    .footer {{
      margin-top: 30px;
      padding-top: 20px;
      border-top: 1px solid #222222;
      font-size: 12px;
      color: #666666;
      line-height: 1.6;
    }}
  </style>
</head>
<body>
  <div class="box">
    <div class="brand">SYNAPSE<span style="color:#888;">.AI</span></div>
    <div class="badge">{badge_text}</div>
    <h1>{status_title}</h1>
    <p>Hi {safe_name},</p>
    <p>{status_msg}</p>

    <div class="quote-box">
      <div class="stars">{stars}</div>
      <div class="quote-text">"{comment.strip()}"</div>
    </div>

    <p style="margin-top:20px;">If you have any further questions or feature requests, you can simply reply to this email.</p>

    <div class="footer">
      Autonomous AI Research Synthesis & Engineering Intelligence.<br>
      © 2026 Synapse AI. All rights reserved.
    </div>
  </div>
</body>
</html>"""

    return send_email(subject, body_text, body_html, recipients=[user_email.strip().lower()], email_type="review_confirmation")


def send_admin_review_notification(
    reviewer_name: str,
    reviewer_email: str,
    rating: int,
    comment: str,
    role: Optional[str] = None,
    is_public: bool = True,
    is_approved: bool = True
) -> Dict[str, Any]:
    """
    Sends an instant notification alert to the site owner (MY_EMAIL) whenever a review or feedback is submitted.
    Particularly critical for PRIVATE reviews so the owner gets notified immediately.
    """
    if not MY_EMAIL:
        return {"success": False, "error": "MY_EMAIL not configured"}

    stars = "★" * max(1, min(5, int(rating))) + "☆" * (5 - max(1, min(5, int(rating))))
    vis_label = "🌐 PUBLIC REVIEW" if is_public else "🔒 PRIVATE FEEDBACK"
    mod_status = "Approved & Live" if (is_public and is_approved) else ("Queued for Moderation (Toxic language flagged)" if not is_approved else "Private (Owner Only)")

    subject = f"[Synapse Feedback] {vis_label}: {reviewer_name} ({rating}★)"

    body_text = f"""New User Feedback Alert:

Reviewer: {reviewer_name}
Email: {reviewer_email}
Role/Affiliation: {role or 'Community Member'}
Rating: {stars} ({rating}/5)
Visibility: {vis_label}
Moderation Status: {mod_status}

Message:
"{comment.strip()}"
"""

    body_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #000000; color: #b5b5b5; padding: 28px 16px; margin: 0; }}
    .card {{ max-width: 560px; margin: auto; background: #050505; border: 1px solid #222222; border-radius: 12px; padding: 32px 28px; }}
    .badge {{ display: inline-block; padding: 5px 12px; border-radius: 999px; font-size: 11px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; background: #141414; border: 1px solid #333333; color: #ffffff; }}
    .stars {{ color: #ffffff; font-size: 16px; letter-spacing: 2px; margin: 10px 0; }}
    .content {{ background: #0c0c0c; border: 1px solid #222222; padding: 16px 18px; border-radius: 6px; font-size: 14px; color: #d4d4d4; margin-top: 14px; line-height: 1.6; font-style: italic; }}
    .meta {{ font-size: 13.5px; color: #888888; line-height: 1.7; margin-top: 20px; border-top: 1px solid #222222; padding-top: 16px; }}
    .meta strong {{ color: #ffffff; font-weight: 600; }}
    .meta a {{ color: #ffffff; text-decoration: underline; }}
  </style>
</head>
<body>
  <div class="card">
    <span class="badge">{'🔒 PRIVATE FEEDBACK' if not is_public else '🌐 PUBLIC REVIEW'}</span>
    <h2 style="margin: 14px 0 6px 0; color:#ffffff; font-size: 22px; font-weight: 800; letter-spacing: -0.02em;">New Feedback Received</h2>
    <div class="stars">{stars} ({rating}/5 Stars)</div>
    
    <div class="content">"{comment.strip()}"</div>

    <div class="meta">
      <strong>Reviewer:</strong> {reviewer_name}<br>
      <strong>Email:</strong> <a href="mailto:{reviewer_email}">{reviewer_email}</a><br>
      <strong>Role:</strong> {role or 'Community Member'}<br>
      <strong>Status:</strong> {mod_status}
    </div>
  </div>
</body>
</html>"""

    return send_email(subject, body_text, body_html, recipients=[MY_EMAIL], email_type="admin_review_alert")


def send_admin_unsubscribe_alert(unsubscriber_email: str, reason: Optional[str] = None) -> Dict[str, Any]:
    """
    Sends an instant notification alert to the founder (MY_EMAIL) whenever a user unsubscribes.
    """
    if not MY_EMAIL:
        return {"success": False, "error": "MY_EMAIL not configured"}

    clean_email = unsubscriber_email.strip().lower()
    now_str = datetime.now().strftime("%B %d, %Y at %I:%M %p UTC")

    subject = f"[Synapse Alert] User Unsubscribed: {clean_email}"
    body_text = f"""User Unsubscribe Notification:

Email: {clean_email}
Timestamp: {now_str}
Reason: {reason or 'User requested 1-click unsubscribe'}

This user has been marked inactive in the MongoDB subscribers database and will no longer receive daily briefs.
"""

    body_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #000000; color: #b5b5b5; padding: 28px 16px; margin: 0; }}
    .card {{ max-width: 560px; margin: auto; background: #050505; border: 1px solid #222222; border-radius: 12px; padding: 32px 28px; }}
    .badge {{ display: inline-block; padding: 5px 12px; border-radius: 999px; font-size: 11px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; background: #1a1a1a; border: 1px solid #333333; color: #ffffff; }}
    h2 {{ color: #ffffff; font-size: 20px; font-weight: 800; margin: 16px 0 8px 0; }}
    .info-box {{ background: #0c0c0c; border: 1px solid #222222; border-radius: 8px; padding: 18px; margin: 16px 0; font-size: 14px; line-height: 1.6; color: #d4d4d4; }}
    .info-box strong {{ color: #ffffff; }}
    .meta {{ font-size: 13px; color: #888888; border-top: 1px solid #222222; padding-top: 16px; margin-top: 20px; }}
  </style>
</head>
<body>
  <div class="card">
    <span class="badge">UNSUBSCRIBE NOTICE</span>
    <h2>A Subscriber Has Unsubscribed</h2>
    <div class="info-box">
      <strong>Email:</strong> {clean_email}<br>
      <strong>Reason:</strong> {reason or 'User requested 1-click unsubscribe'}<br>
      <strong>Time:</strong> {now_str}
    </div>
    <p>This email has been deactivated in MongoDB Atlas subscribers. All automated daily AI briefing dispatches to this address have been halted.</p>
    <div class="meta">
      Synapse AI Autonomous Audit Telemetry
    </div>
  </div>
</body>
</html>"""

    return send_email(subject, body_text, body_html, recipients=[MY_EMAIL], email_type="admin_unsubscribe_alert")


