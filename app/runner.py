import logging
from typing import List, Dict, Any
from .config import YOUTUBE_CHANNELS
from .scrapers.youtube import YouTubeScraper
from .scrapers.openai import OpenAIScraper
from .scrapers.anthropic import AnthropicScraper
from .scrapers.huggingface import HuggingFaceScraper
from .scrapers.techcrunch import TechCrunchScraper
from .scrapers.arxiv_ai import ArxivScraper
from .database.repository import Repository

logger = logging.getLogger(__name__)


def run_scrapers(hours: int = 24) -> dict:
    youtube_scraper = YouTubeScraper()
    openai_scraper = OpenAIScraper()
    anthropic_scraper = AnthropicScraper()
    hf_scraper = HuggingFaceScraper()
    tc_scraper = TechCrunchScraper()
    arxiv_scraper = ArxivScraper()
    repo = Repository()
    
    # 1. YouTube Videos
    youtube_videos = []
    video_dicts = []
    for channel_id in YOUTUBE_CHANNELS:
        try:
            videos = youtube_scraper.get_latest_videos(channel_id, hours=hours)
            youtube_videos.extend(videos)
            video_dicts.extend([
                {
                    "video_id": v.video_id,
                    "title": v.title,
                    "url": v.url,
                    "channel_id": channel_id,
                    "published_at": v.published_at,
                    "description": v.description,
                    "transcript": v.transcript
                }
                for v in videos
            ])
        except Exception as e:
            logger.warning(f"Failed to scrape YouTube channel {channel_id}: {e}")
    
    if video_dicts:
        repo.bulk_create_youtube_videos(video_dicts)
    
    # 2. OpenAI Articles
    try:
        openai_articles = openai_scraper.get_articles(hours=hours)
        if openai_articles:
            repo.bulk_create_openai_articles([
                {
                    "guid": a.guid,
                    "title": a.title,
                    "url": a.url,
                    "published_at": a.published_at,
                    "description": a.description,
                    "category": a.category
                }
                for a in openai_articles
            ])
    except Exception as e:
        logger.warning(f"Failed to scrape OpenAI feed: {e}")
        openai_articles = []
    
    # 3. Anthropic Articles
    try:
        anthropic_articles = anthropic_scraper.get_articles(hours=hours)
        if anthropic_articles:
            repo.bulk_create_anthropic_articles([
                {
                    "guid": a.guid,
                    "title": a.title,
                    "url": a.url,
                    "published_at": a.published_at,
                    "description": a.description,
                    "category": a.category
                }
                for a in anthropic_articles
            ])
    except Exception as e:
        logger.warning(f"Failed to scrape Anthropic feed: {e}")
        anthropic_articles = []
    
    # 4. Hugging Face Articles
    try:
        hf_articles = hf_scraper.get_articles(hours=hours)
        if hf_articles:
            repo.bulk_create_huggingface_articles([
                {
                    "guid": a.guid,
                    "title": a.title,
                    "url": a.url,
                    "published_at": a.published_at,
                    "description": a.description,
                    "category": a.category
                }
                for a in hf_articles
            ])
    except Exception as e:
        logger.warning(f"Failed to scrape HuggingFace feed: {e}")
        hf_articles = []

    # 5. TechCrunch AI Articles
    try:
        tc_articles = tc_scraper.get_articles(hours=hours)
        if tc_articles:
            repo.bulk_create_techcrunch_articles([
                {
                    "guid": a.guid,
                    "title": a.title,
                    "url": a.url,
                    "published_at": a.published_at,
                    "description": a.description,
                    "category": a.category
                }
                for a in tc_articles
            ])
    except Exception as e:
        logger.warning(f"Failed to scrape TechCrunch feed: {e}")
        tc_articles = []

    # 6. arXiv AI Research Papers
    try:
        arxiv_articles = arxiv_scraper.get_articles(hours=hours)
        if arxiv_articles:
            repo.bulk_create_arxiv_articles([
                {
                    "guid": a.guid,
                    "title": a.title,
                    "url": a.url,
                    "published_at": a.published_at,
                    "description": a.description,
                    "category": a.category
                }
                for a in arxiv_articles
            ])
    except Exception as e:
        logger.warning(f"Failed to scrape arXiv feed: {e}")
        arxiv_articles = []
    
    return {
        "youtube": youtube_videos,
        "openai": openai_articles,
        "anthropic": anthropic_articles,
        "huggingface": hf_articles,
        "techcrunch": tc_articles,
        "arxiv": arxiv_articles,
    }


if __name__ == "__main__":
    results = run_scrapers(hours=24)
    print(f"YouTube videos: {len(results['youtube'])}")
    print(f"OpenAI articles: {len(results['openai'])}")
    print(f"Anthropic articles: {len(results['anthropic'])}")
    print(f"HuggingFace articles: {len(results['huggingface'])}")
    print(f"TechCrunch articles: {len(results['techcrunch'])}")
    print(f"arXiv articles: {len(results['arxiv'])}")
