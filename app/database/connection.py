import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from app.database.models import Base

load_dotenv()
logger = logging.getLogger(__name__)

# MongoDB Atlas Configuration
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "ai_news_aggregator")

_mongo_client = None
_mongo_db = None
_mongo_last_failure_time = 0.0


def get_mongo_db():
    """
    Returns active MongoDB database instance if MONGODB_URI is configured and reachable.
    Caches connection client for high performance.
    """
    global _mongo_client, _mongo_db, _mongo_last_failure_time
    if _mongo_db is not None:
        return _mongo_db

    if not MONGODB_URI:
        return None

    import time
    if time.time() - _mongo_last_failure_time < 60.0:
        return None

    try:
        import pymongo
        import certifi
        client = pymongo.MongoClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=10000,
            tlsCAFile=certifi.where()
        )
        client.admin.command("ping")
        _mongo_client = client
        _mongo_db = client[MONGODB_DB_NAME]
        logger.info(f"Connected successfully to MongoDB Atlas database: {MONGODB_DB_NAME}")
        return _mongo_db
    except Exception as e:
        _mongo_last_failure_time = time.time()
        logger.warning(f"MongoDB Atlas connection attempt notice: {e}")
        return None


def get_database_url() -> str:
    """
    Returns database URL. Defaults to SQLite if POSTGRES is not configured or offline.
    """
    db_type = os.getenv("DB_TYPE", "").lower()
    if db_type == "sqlite":
        db_path = os.getenv("SQLITE_PATH", "ai_news.db")
        return f"sqlite:///{db_path}"

    custom_url = os.getenv("DATABASE_URL")
    if custom_url:
        return custom_url

    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "ai_news_aggregator")

    pg_url = f"postgresql://{user}:{password}@{host}:{port}/{db}"
    return pg_url


def create_db_engine():
    # In-memory SQLite only if explicitly invoked by legacy SQLAlchemy tests or CI
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    try:
        Base.metadata.create_all(bind=eng)
    except Exception as e:
        logger.warning(f"Could not create SQLite metadata tables: {e}")
    return eng


engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initializes collections and indexes directly in MongoDB Atlas and SQLite fallback."""
    mongo_db = get_mongo_db()
    if mongo_db is not None:
        try:
            mongo_db["subscribers"].create_index("email", unique=True)
            mongo_db["users"].create_index("email", unique=True)
            mongo_db["digests"].create_index("id", unique=True)
            mongo_db["digests"].create_index("created_at")
            mongo_db["youtube_videos"].create_index("video_id", unique=True)
            mongo_db["openai_articles"].create_index("guid", unique=True)
            mongo_db["anthropic_articles"].create_index("guid", unique=True)
            mongo_db["arxiv_articles"].create_index("guid", unique=True)
            mongo_db["huggingface_articles"].create_index("guid", unique=True)
            mongo_db["techcrunch_articles"].create_index("guid", unique=True)
            mongo_db["reviews"].create_index("id", unique=True)
            mongo_db["reviews"].create_index([("is_approved", 1), ("is_public", 1), ("timestamp", -1)])
            logger.info("✓ MongoDB Atlas collections & indexes initialized successfully!")
        except Exception as err:
            logger.warning(f"Could not build MongoDB indexes: {err}")
    else:
        logger.info("Initializing fallback SQLite schema for CI testing...")
        try:
            Base.metadata.create_all(bind=engine)
        except Exception as e:
            logger.warning(f"Could not initialize fallback tables: {e}")


def get_session():
    return SessionLocal()
