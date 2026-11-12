import os
from dotenv import load_dotenv

load_dotenv()

# YouTube Channels to Monitor
YOUTUBE_CHANNELS = [
    "UCawZsQWqfGSbCI5yjkdVkTA",  # Matthew Berman
    "UCn8ujwUInbJkBhffxqAPBVQ",  # Dave Ebbelaar
    "UCv83tO5cePwHMt1952IVVHw",  # AI Explained
    "UCbfYPyITQ-EY778Z-uh8ErQ",  # Two Minute Papers
]

# RSS Feeds for AI Research & Industry News
RSS_FEEDS = {
    "openai": "https://openai.com/news/rss.xml",
    "anthropic": "https://www.anthropic.com/news/rss",
    "huggingface": "https://huggingface.co/blog/feed.xml",
    "techcrunch_ai": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "arxiv_ai": "http://export.arxiv.org/rss/cs.AI",
    "deepmind": "https://deepmind.google/blog/rss.xml",
}

# Groq LLM Inference Settings
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
_env_model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_MODEL = "openai/gpt-oss-120b" if ("llama" in _env_model.lower() or not _env_model.strip()) else _env_model
GROQ_FALLBACK_MODEL = "qwen/qwen3.8-27b"

# Pipeline Defaults
DEFAULT_HOURS = int(os.getenv("DEFAULT_HOURS", "24"))
DEFAULT_TOP_N = int(os.getenv("DEFAULT_TOP_N", "10"))
DIGEST_OUTPUT_DIR = os.getenv("DIGEST_OUTPUT_DIR", "output/digests")

# Email Settings
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "false").lower() in ("true", "1", "yes")
MY_EMAIL = os.getenv("MY_EMAIL", "")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
RECIPIENTS = [e.strip() for e in os.getenv("RECIPIENTS", "").split(",") if e.strip()] or ([MY_EMAIL] if MY_EMAIL else [])


