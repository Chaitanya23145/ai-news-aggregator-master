import logging
from datetime import datetime, timezone, timedelta
from typing import List
from pydantic import BaseModel
import feedparser
from app.config import RSS_FEEDS

logger = logging.getLogger(__name__)


class TechCrunchArticle(BaseModel):
    guid: str
    title: str
    url: str
    published_at: datetime
    description: str
    category: str = "TechCrunch AI"


class TechCrunchScraper:
    def __init__(self, rss_url: str = None):
        self.rss_url = rss_url or RSS_FEEDS.get("techcrunch_ai", "https://techcrunch.com/category/artificial-intelligence/feed/")

    def get_articles(self, hours: int = 24) -> List[TechCrunchArticle]:
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
                    title = entry.get("title", "Untitled")
                    url = entry.get("link", "")
                    description = entry.get("summary") or entry.get("description", "")

                    articles.append(
                        TechCrunchArticle(
                            guid=guid,
                            title=title,
                            url=url,
                            published_at=published,
                            description=description,
                            category="TechCrunch AI"
                        )
                    )
            except Exception as e:
                logger.warning(f"Error parsing TechCrunch feed item: {e}")

        logger.info(f"Retrieved {len(articles)} TechCrunch AI articles from past {hours} hours")
        return articles
