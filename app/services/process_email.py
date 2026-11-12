import os
import logging
from dotenv import load_dotenv

load_dotenv()

from app.agent.email_agent import EmailAgent, RankedArticleDetail, EmailDigestResponse
from app.agent.curator_agent import CuratorAgent
from app.profiles.user_profile import USER_PROFILE
from app.database.repository import Repository
from app.services.email import send_email, digest_to_html
from app.services.digest_exporter import DigestExporter
from app.config import EMAIL_ENABLED, MY_EMAIL, APP_PASSWORD

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def generate_email_digest(hours: int = 24, top_n: int = 10) -> EmailDigestResponse:
    curator = CuratorAgent(USER_PROFILE)
    email_agent = EmailAgent(USER_PROFILE)
    repo = Repository()
    
    digests = repo.get_recent_digests(hours=hours)
    total = len(digests)
    
    if total == 0:
        logger.warning(f"No digests found from the last {hours} hours, expanding search window...")
        digests = repo.get_recent_digests(hours=168)
        total = len(digests)
    
    if total == 0:
        logger.info("No digests available in database, seeding frontier AI digests...")
        from app.services.demo_data import seed_demo_digests
        seed_demo_digests(repo)
        digests = repo.get_recent_digests(hours=hours) or repo.get_recent_digests(hours=168)
        total = len(digests)

    if total == 0:
        logger.warning("No digests available to rank.")
        raise ValueError("No digests available")
    
    logger.info(f"Ranking {total} digests for email generation")
    ranked_articles = curator.rank_digests(digests)
    
    if not ranked_articles:
        logger.error("Failed to rank digests")
        raise ValueError("Failed to rank articles")
    
    logger.info(f"Generating email digest with top {top_n} articles")
    
    article_details = [
        RankedArticleDetail(
            digest_id=a.digest_id,
            rank=a.rank,
            relevance_score=a.relevance_score,
            reasoning=a.reasoning,
            title=next((d["title"] for d in digests if d["id"] == a.digest_id), ""),
            summary=next((d["summary"] for d in digests if d["id"] == a.digest_id), ""),
            url=next((d["url"] for d in digests if d["id"] == a.digest_id), ""),
            article_type=next((d["article_type"] for d in digests if d["id"] == a.digest_id), "")
        )
        for a in ranked_articles
    ]
    
    email_digest = email_agent.create_email_digest_response(
        ranked_articles=article_details,
        total_ranked=len(ranked_articles),
        limit=top_n
    )
    
    logger.info("Email digest generated successfully")
    logger.info(f"\n=== Email Introduction ===")
    logger.info(email_digest.introduction.greeting)
    logger.info(f"\n{email_digest.introduction.introduction}")
    
    return email_digest


def send_digest_email(hours: int = 24, top_n: int = 10) -> dict:
    try:
        result = generate_email_digest(hours=hours, top_n=top_n)
        markdown_content = result.to_markdown()
        html_content = digest_to_html(result)
        
        subject = f"Daily AI News Digest - {result.introduction.greeting.split('for ')[-1] if 'for ' in result.introduction.greeting else 'Today'}"
        
        # Always export locally
        exporter = DigestExporter()
        export_info = exporter.export_digest(result)

        email_sent = False
        if EMAIL_ENABLED and MY_EMAIL and APP_PASSWORD:
            try:
                # Dispatch to all registered subscribed users and admin
                repo = Repository()
                subscribers = repo.get_all_subscriber_emails()
                if MY_EMAIL and MY_EMAIL not in subscribers:
                    subscribers.append(MY_EMAIL)

                dispatch_res = send_email(
                    subject=subject,
                    body_text=markdown_content,
                    body_html=html_content,
                    recipients=subscribers
                )
                email_sent = dispatch_res.get("success", False)
                if email_sent:
                    logger.info(f"Email sent successfully to {len(subscribers)} subscribers!")
                else:
                    logger.warning(f"Email dispatch completed with notice: {dispatch_res.get('error')}")
            except Exception as mail_err:
                logger.warning(f"Failed to send email ({mail_err}), digest is saved to disk.")
        else:
            logger.info("Email delivery skipped (EMAIL_ENABLED=false or credentials not configured). Digest saved locally.")
        
        return {
            "success": True,
            "subject": subject,
            "articles_count": len(result.articles),
            "email_sent": email_sent,
            "exported_markdown": export_info["markdown_path"]
        }
    except ValueError as e:
        logger.error(f"Error generating/sending digest: {e}")
        return {
            "success": False,
            "error": str(e)
        }


if __name__ == "__main__":
    res = send_digest_email(hours=24, top_n=10)
    if res["success"]:
        print(f"\n=== Email Digest Created ===\nSubject: {res['subject']}\nArticles: {res['articles_count']}")
    else:
        print(f"Error: {res.get('error')}")
