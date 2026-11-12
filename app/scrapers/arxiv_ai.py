import logging
from datetime import datetime, timezone, timedelta
from typing import List
from pydantic import BaseModel
import feedparser
from app.config import RSS_FEEDS

logger = logging.getLogger(__name__)


class ArxivArticle(BaseModel):
    guid: str
    title: str
    url: str
    published_at: datetime
    description: str
    category: str = "arXiv AI"


class ArxivScraper:
    def __init__(self, rss_url: str = None):
        self.rss_url = rss_url or RSS_FEEDS.get("arxiv_ai", "http://export.arxiv.org/rss/cs.AI")

    def get_articles(self, hours: int = 48) -> List[ArxivArticle]:
        feed = feedparser.parse(self.rss_url)
        articles = []
        time_limit = datetime.now(timezone.utc) - timedelta(hours=hours)

        for entry in feed.entries:
            try:
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                else:
                    published = datetime.now(timezone.utc)

                if published >= time_limit:
                    guid = entry.get("id") or entry.get("link") or entry.get("title")
                    raw_title = entry.get("title", "Untitled Paper")
                    title = raw_title.replace("\n", " ").strip()
                    url = entry.get("link", "")
                    description = entry.get("summary", "").replace("\n", " ").strip()

                    articles.append(
                        ArxivArticle(
                            guid=guid,
                            title=title,
                            url=url,
                            published_at=published,
                            description=description,
                            category="arXiv AI"
                        )
                    )
            except Exception as e:
                logger.warning(f"Error parsing arXiv feed item: {e}")

        logger.info(f"Retrieved {len(articles)} arXiv AI papers from past {hours} hours")
        return articles
