import logging
from datetime import datetime, timezone, timedelta
from typing import List
from pydantic import BaseModel
import feedparser
from app.config import RSS_FEEDS

logger = logging.getLogger(__name__)


class HuggingFaceArticle(BaseModel):
    guid: str
    title: str
    url: str
    published_at: datetime
    description: str
    category: str = "HuggingFace"


class HuggingFaceScraper:
    def __init__(self, rss_url: str = None):
        self.rss_url = rss_url or RSS_FEEDS.get("huggingface", "https://huggingface.co/blog/feed.xml")

    def get_articles(self, hours: int = 24) -> List[HuggingFaceArticle]:
        feed = feedparser.parse(self.rss_url)
        articles = []
        time_limit = datetime.now(timezone.utc) - timedelta(hours=hours)

        for entry in feed.entries:
            try:
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    published = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
                else:
                    published = datetime.now(timezone.utc)

                if published >= time_limit:
                    guid = entry.get("id") or entry.get("link") or entry.get("title")
                    title = entry.get("title", "Untitled")
                    url = entry.get("link", "")
                    description = entry.get("summary") or entry.get("description", "")

                    articles.append(
                        HuggingFaceArticle(
                            guid=guid,
                            title=title,
                            url=url,
                            published_at=published,
                            description=description,
                            category="HuggingFace"
                        )
                    )
            except Exception as e:
                logger.warning(f"Error parsing HuggingFace feed item: {e}")

        logger.info(f"Retrieved {len(articles)} Hugging Face articles from past {hours} hours")
        return articles
