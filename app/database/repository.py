import hashlib
import os
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from .models import YouTubeVideo, OpenAIArticle, AnthropicArticle, Digest, User, Subscriber, Review
from .connection import get_session, get_mongo_db

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 100000)
    return f"{salt}${key.hex()}"


def verify_password(stored_password_hash: str, password: str) -> bool:
    try:
        salt, key_hex = stored_password_hash.split("$")
        check_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 100000)
        return check_key.hex() == key_hex
    except Exception:
        return False


class MongoEntity:
    """Generic wrapper for MongoDB documents providing attribute access."""
    def __init__(self, doc: dict):
        self._doc = doc or {}
        for k, v in self._doc.items():
            setattr(self, k, v)


class Repository:
    def __init__(self, session: Optional[Session] = None):
        if session is not None:
            self.session = session
            self.mongo_db = None
        else:
            self.mongo_db = get_mongo_db()
            if self.mongo_db is not None:
                self.session = None
            else:
                # SQLite fallback: always ensure tables exist before use
                from app.database.connection import Base, engine
                try:
                    Base.metadata.create_all(bind=engine)
                except Exception:
                    pass
                self.session = get_session()

    # ---------------- YouTube Videos ----------------
    def create_youtube_video(self, video_id: str, title: str, url: str, channel_id: str, 
                            published_at: datetime, description: str = "", transcript: Optional[str] = None):
        if self.mongo_db is not None:
            existing = self.mongo_db["youtube_videos"].find_one({"video_id": video_id})
            if existing:
                return None
            doc = {
                "video_id": video_id,
                "title": title,
                "url": url,
                "channel_id": channel_id,
                "published_at": published_at,
                "description": description,
                "transcript": transcript,
                "created_at": datetime.utcnow()
            }
            self.mongo_db["youtube_videos"].insert_one(doc)
            return MongoEntity(doc)

        existing = self.session.query(YouTubeVideo).filter_by(video_id=video_id).first()
        if existing:
            return None
        video = YouTubeVideo(
            video_id=video_id,
            title=title,
            url=url,
            channel_id=channel_id,
            published_at=published_at,
            description=description,
            transcript=transcript
        )
        self.session.add(video)
        self.session.commit()
        return video

    def bulk_create_youtube_videos(self, videos: List[dict]) -> int:
        if self.mongo_db is not None:
            inserted = 0
            for v in videos:
                if not self.mongo_db["youtube_videos"].find_one({"video_id": v["video_id"]}):
                    doc = {
                        "video_id": v["video_id"],
                        "title": v["title"],
                        "url": v["url"],
                        "channel_id": v.get("channel_id", ""),
                        "published_at": v["published_at"],
                        "description": v.get("description", ""),
                        "transcript": v.get("transcript"),
                        "created_at": datetime.utcnow()
                    }
                    self.mongo_db["youtube_videos"].insert_one(doc)
                    inserted += 1
            return inserted

        new_videos = []
        for v in videos:
            existing = self.session.query(YouTubeVideo).filter_by(video_id=v["video_id"]).first()
            if not existing:
                new_videos.append(YouTubeVideo(
                    video_id=v["video_id"],
                    title=v["title"],
                    url=v["url"],
                    channel_id=v.get("channel_id", ""),
                    published_at=v["published_at"],
                    description=v.get("description", ""),
                    transcript=v.get("transcript")
                ))
        if new_videos:
            self.session.add_all(new_videos)
            self.session.commit()
        return len(new_videos)

    def get_youtube_videos_without_transcript(self, limit: Optional[int] = None):
        if self.mongo_db is not None:
            cursor = self.mongo_db["youtube_videos"].find({
                "$or": [{"transcript": None}, {"transcript": {"$exists": False}}]
            })
            if limit:
                cursor = cursor.limit(limit)
            return [MongoEntity(d) for d in cursor]

        query = self.session.query(YouTubeVideo).filter(YouTubeVideo.transcript.is_(None))
        if limit:
            query = query.limit(limit)
        return query.all()

    def update_youtube_video_transcript(self, video_id: str, transcript: str) -> bool:
        if self.mongo_db is not None:
            res = self.mongo_db["youtube_videos"].update_one(
                {"video_id": video_id},
                {"$set": {"transcript": transcript}}
            )
            return res.modified_count > 0

        video = self.session.query(YouTubeVideo).filter_by(video_id=video_id).first()
        if video:
            video.transcript = transcript
            self.session.commit()
            return True
        return False

    # ---------------- OpenAI Articles ----------------
    def create_openai_article(self, guid: str, title: str, url: str, published_at: datetime,
                              description: str = "", category: Optional[str] = None):
        if self.mongo_db is not None:
            existing = self.mongo_db["openai_articles"].find_one({"guid": guid})
            if existing:
                return None
            doc = {
                "guid": guid,
                "title": title,
                "url": url,
                "published_at": published_at,
                "description": description,
                "category": category,
                "created_at": datetime.utcnow()
            }
            self.mongo_db["openai_articles"].insert_one(doc)
            return MongoEntity(doc)

        existing = self.session.query(OpenAIArticle).filter_by(guid=guid).first()
        if existing:
            return None
        article = OpenAIArticle(
            guid=guid,
            title=title,
            url=url,
            published_at=published_at,
            description=description,
            category=category
        )
        self.session.add(article)
        self.session.commit()
        return article

    def bulk_create_openai_articles(self, articles: List[dict]) -> int:
        if self.mongo_db is not None:
            inserted = 0
            for a in articles:
                if not self.mongo_db["openai_articles"].find_one({"guid": a["guid"]}):
                    doc = {
                        "guid": a["guid"],
                        "title": a["title"],
                        "url": a["url"],
                        "published_at": a["published_at"],
                        "description": a.get("description", ""),
                        "category": a.get("category"),
                        "created_at": datetime.utcnow()
                    }
                    self.mongo_db["openai_articles"].insert_one(doc)
                    inserted += 1
            return inserted

        new_articles = []
        for a in articles:
            existing = self.session.query(OpenAIArticle).filter_by(guid=a["guid"]).first()
            if not existing:
                new_articles.append(OpenAIArticle(
                    guid=a["guid"],
                    title=a["title"],
                    url=a["url"],
                    published_at=a["published_at"],
                    description=a.get("description", ""),
                    category=a.get("category")
                ))
        if new_articles:
            self.session.add_all(new_articles)
            self.session.commit()
        return len(new_articles)

    # ---------------- Anthropic Articles ----------------
    def create_anthropic_article(self, guid: str, title: str, url: str, published_at: datetime,
                                 description: str = "", category: Optional[str] = None):
        if self.mongo_db is not None:
            existing = self.mongo_db["anthropic_articles"].find_one({"guid": guid})
            if existing:
                return None
            doc = {
                "guid": guid,
                "title": title,
                "url": url,
                "published_at": published_at,
                "description": description,
                "category": category,
                "markdown": None,
                "created_at": datetime.utcnow()
            }
            self.mongo_db["anthropic_articles"].insert_one(doc)
            return MongoEntity(doc)

        existing = self.session.query(AnthropicArticle).filter_by(guid=guid).first()
        if existing:
            return None
        article = AnthropicArticle(
            guid=guid,
            title=title,
            url=url,
            published_at=published_at,
            description=description,
            category=category
        )
        self.session.add(article)
        self.session.commit()
        return article

    def bulk_create_anthropic_articles(self, articles: List[dict]) -> int:
        if self.mongo_db is not None:
            inserted = 0
            for a in articles:
                if not self.mongo_db["anthropic_articles"].find_one({"guid": a["guid"]}):
                    doc = {
                        "guid": a["guid"],
                        "title": a["title"],
                        "url": a["url"],
                        "published_at": a["published_at"],
                        "description": a.get("description", ""),
                        "category": a.get("category"),
                        "markdown": None,
                        "created_at": datetime.utcnow()
                    }
                    self.mongo_db["anthropic_articles"].insert_one(doc)
                    inserted += 1
            return inserted

        new_articles = []
        for a in articles:
            existing = self.session.query(AnthropicArticle).filter_by(guid=a["guid"]).first()
            if not existing:
                new_articles.append(AnthropicArticle(
                    guid=a["guid"],
                    title=a["title"],
                    url=a["url"],
                    published_at=a["published_at"],
                    description=a.get("description", ""),
                    category=a.get("category")
                ))
        if new_articles:
            self.session.add_all(new_articles)
            self.session.commit()
        return len(new_articles)

    def get_anthropic_articles_without_markdown(self, limit: Optional[int] = None):
        if self.mongo_db is not None:
            cursor = self.mongo_db["anthropic_articles"].find({
                "$or": [{"markdown": None}, {"markdown": {"$exists": False}}]
            })
            if limit:
                cursor = cursor.limit(limit)
            return [MongoEntity(d) for d in cursor]

        query = self.session.query(AnthropicArticle).filter(AnthropicArticle.markdown.is_(None))
        if limit:
            query = query.limit(limit)
        return query.all()

    def update_anthropic_article_markdown(self, guid: str, markdown: str) -> bool:
        if self.mongo_db is not None:
            res = self.mongo_db["anthropic_articles"].update_one(
                {"guid": guid},
                {"$set": {"markdown": markdown}}
            )
            return res.modified_count > 0

        article = self.session.query(AnthropicArticle).filter_by(guid=guid).first()
        if article:
            article.markdown = markdown
            self.session.commit()
            return True
        return False

    def bulk_create_arxiv_articles(self, articles: List[dict]) -> int:
        if self.mongo_db is not None:
            inserted = 0
            for a in articles:
                if not self.mongo_db["arxiv_articles"].find_one({"guid": a["guid"]}):
                    doc = {
                        "guid": a["guid"],
                        "title": a["title"],
                        "url": a["url"],
                        "published_at": a["published_at"],
                        "description": a.get("description", ""),
                        "category": a.get("category", "arXiv AI"),
                        "created_at": datetime.now(timezone.utc)
                    }
                    self.mongo_db["arxiv_articles"].insert_one(doc)
                    inserted += 1
            return inserted
        return len(articles)

    def bulk_create_huggingface_articles(self, articles: List[dict]) -> int:
        if self.mongo_db is not None:
            inserted = 0
            for a in articles:
                if not self.mongo_db["huggingface_articles"].find_one({"guid": a["guid"]}):
                    doc = {
                        "guid": a["guid"],
                        "title": a["title"],
                        "url": a["url"],
                        "published_at": a["published_at"],
                        "description": a.get("description", ""),
                        "category": a.get("category", "HuggingFace"),
                        "created_at": datetime.now(timezone.utc)
                    }
                    self.mongo_db["huggingface_articles"].insert_one(doc)
                    inserted += 1
            return inserted
        return len(articles)

    def bulk_create_techcrunch_articles(self, articles: List[dict]) -> int:
        if self.mongo_db is not None:
            inserted = 0
            for a in articles:
                if not self.mongo_db["techcrunch_articles"].find_one({"guid": a["guid"]}):
                    doc = {
                        "guid": a["guid"],
                        "title": a["title"],
                        "url": a["url"],
                        "published_at": a["published_at"],
                        "description": a.get("description", ""),
                        "category": a.get("category", "TechCrunch AI"),
                        "created_at": datetime.now(timezone.utc)
                    }
                    self.mongo_db["techcrunch_articles"].insert_one(doc)
                    inserted += 1
            return inserted
        return len(articles)

    # ---------------- Digests Processing ----------------
    def get_articles_without_digest(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        articles = []
        seen_ids = set()

        if self.mongo_db is not None:
            for d in self.mongo_db["digests"].find({}, {"id": 1, "article_type": 1, "article_id": 1}):
                key = d.get("id") or f"{d.get('article_type')}:{d.get('article_id')}"
                seen_ids.add(key)

            # YouTube
            for v in self.mongo_db["youtube_videos"].find({"transcript": {"$nin": [None, "__UNAVAILABLE__"]}}):
                key = f"youtube:{v['video_id']}"
                if key not in seen_ids:
                    articles.append({
                        "type": "youtube",
                        "id": v["video_id"],
                        "title": v.get("title", ""),
                        "url": v.get("url", ""),
                        "content": v.get("transcript") or v.get("description") or "",
                        "published_at": v.get("published_at")
                    })

            # OpenAI
            for o in self.mongo_db["openai_articles"].find():
                key = f"openai:{o['guid']}"
                if key not in seen_ids:
                    articles.append({
                        "type": "openai",
                        "id": o["guid"],
                        "title": o.get("title", ""),
                        "url": o.get("url", ""),
                        "content": o.get("description") or "",
                        "published_at": o.get("published_at")
                    })

            # Anthropic
            for a in self.mongo_db["anthropic_articles"].find({"markdown": {"$ne": None}}):
                key = f"anthropic:{a['guid']}"
                if key not in seen_ids:
                    articles.append({
                        "type": "anthropic",
                        "id": a["guid"],
                        "title": a.get("title", ""),
                        "url": a.get("url", ""),
                        "content": a.get("markdown") or a.get("description") or "",
                        "published_at": a.get("published_at")
                    })

            # arXiv AI
            for ar in self.mongo_db["arxiv_articles"].find():
                key = f"arxiv_ai:{ar['guid']}"
                if key not in seen_ids:
                    articles.append({
                        "type": "arxiv_ai",
                        "id": ar["guid"],
                        "title": ar.get("title", ""),
                        "url": ar.get("url", ""),
                        "content": ar.get("description") or "",
                        "published_at": ar.get("published_at")
                    })

            # Hugging Face
            for hf in self.mongo_db["huggingface_articles"].find():
                key = f"huggingface:{hf['guid']}"
                if key not in seen_ids:
                    articles.append({
                        "type": "huggingface",
                        "id": hf["guid"],
                        "title": hf.get("title", ""),
                        "url": hf.get("url", ""),
                        "content": hf.get("description") or "",
                        "published_at": hf.get("published_at")
                    })

            # TechCrunch AI
            for tc in self.mongo_db["techcrunch_articles"].find():
                key = f"techcrunch_ai:{tc['guid']}"
                if key not in seen_ids:
                    articles.append({
                        "type": "techcrunch_ai",
                        "id": tc["guid"],
                        "title": tc.get("title", ""),
                        "url": tc.get("url", ""),
                        "content": tc.get("description") or "",
                        "published_at": tc.get("published_at")
                    })

            if limit:
                articles = articles[:limit]
            return articles

        # SQL Fallback
        digests = self.session.query(Digest).all()
        for d in digests:
            seen_ids.add(f"{d.article_type}:{d.article_id}")

        youtube_videos = self.session.query(YouTubeVideo).filter(
            YouTubeVideo.transcript.isnot(None),
            YouTubeVideo.transcript != "__UNAVAILABLE__"
        ).all()
        for video in youtube_videos:
            key = f"youtube:{video.video_id}"
            if key not in seen_ids:
                articles.append({
                    "type": "youtube",
                    "id": video.video_id,
                    "title": video.title,
                    "url": video.url,
                    "content": video.transcript or video.description or "",
                    "published_at": video.published_at
                })

        openai_articles = self.session.query(OpenAIArticle).all()
        for article in openai_articles:
            key = f"openai:{article.guid}"
            if key not in seen_ids:
                articles.append({
                    "type": "openai",
                    "id": article.guid,
                    "title": article.title,
                    "url": article.url,
                    "content": article.description or "",
                    "published_at": article.published_at
                })

        anthropic_articles = self.session.query(AnthropicArticle).filter(
            AnthropicArticle.markdown.isnot(None)
        ).all()
        for article in anthropic_articles:
            key = f"anthropic:{article.guid}"
            if key not in seen_ids:
                articles.append({
                    "type": "anthropic",
                    "id": article.guid,
                    "title": article.title,
                    "url": article.url,
                    "content": article.markdown or article.description or "",
                    "published_at": article.published_at
                })

        if limit:
            articles = articles[:limit]
        return articles

    def create_digest(self, article_type: str, article_id: str, url: str, title: str, summary: str, published_at: Optional[datetime] = None):
        digest_id = f"{article_type}:{article_id}"
        
        if published_at:
            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=timezone.utc)
            created_at = published_at
        else:
            created_at = datetime.now(timezone.utc)

        if self.mongo_db is not None:
            existing = self.mongo_db["digests"].find_one({"id": digest_id})
            if existing:
                return None
            doc = {
                "id": digest_id,
                "article_type": article_type,
                "article_id": article_id,
                "url": url,
                "title": title,
                "summary": summary,
                "created_at": created_at
            }
            self.mongo_db["digests"].insert_one(doc)
            return MongoEntity(doc)

        existing = self.session.query(Digest).filter_by(id=digest_id).first()
        if existing:
            return None
        digest = Digest(
            id=digest_id,
            article_type=article_type,
            article_id=article_id,
            url=url,
            title=title,
            summary=summary,
            created_at=created_at
        )
        self.session.add(digest)
        self.session.commit()
        return digest

    def get_recent_digests(self, hours: Optional[int] = 24, article_type: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
        if self.mongo_db is not None:
            filter_query: Dict[str, Any] = {}
            if hours and hours > 0:
                cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
                # Compare both timezone aware or naive
                cutoff_naive = cutoff.replace(tzinfo=None)
                filter_query["$or"] = [
                    {"created_at": {"$gte": cutoff}},
                    {"created_at": {"$gte": cutoff_naive}}
                ]

            if article_type and article_type.lower() != "all":
                filter_query["article_type"] = article_type.lower()

            if search:
                pattern = {"$regex": search, "$options": "i"}
                search_condition = {"$or": [{"title": pattern}, {"summary": pattern}]}
                if "$or" in filter_query:
                    filter_query = {"$and": [filter_query, search_condition]}
                else:
                    filter_query.update(search_condition)

            cursor = self.mongo_db["digests"].find(filter_query).sort("created_at", -1)
            results = []
            for d in cursor:
                results.append({
                    "id": d.get("id"),
                    "article_type": d.get("article_type"),
                    "article_id": d.get("article_id"),
                    "url": d.get("url"),
                    "title": d.get("title"),
                    "summary": d.get("summary"),
                    "created_at": d.get("created_at")
                })
            return results

        # SQL Fallback
        try:
            query = self.session.query(Digest)
            if hours and hours > 0:
                cutoff_utc = datetime.now(timezone.utc) - timedelta(hours=hours)
                cutoff_naive = cutoff_utc.replace(tzinfo=None)
                query = query.filter((Digest.created_at >= cutoff_utc) | (Digest.created_at >= cutoff_naive))

            if article_type and article_type.lower() != "all":
                query = query.filter(Digest.article_type == article_type.lower())

            if search:
                pattern = f"%{search}%"
                query = query.filter(
                    (Digest.title.ilike(pattern)) | (Digest.summary.ilike(pattern))
                )

            digests = query.order_by(Digest.created_at.desc()).all()
            return [
                {
                    "id": d.id,
                    "article_type": d.article_type,
                    "article_id": d.article_id,
                    "url": d.url,
                    "title": d.title,
                    "summary": d.summary,
                    "created_at": d.created_at
                }
                for d in digests
            ]
        except Exception as e:
            logger.warning(f"SQLite fallback query failed, attempting table init: {e}")
            try:
                from app.database.connection import Base, engine
                Base.metadata.create_all(bind=engine)
                return []
            except Exception:
                return []

    # ---------------- SaaS User Management ----------------
    def create_user(self, email: str, password: str, name: Optional[str] = None, email_subscribed: bool = True):
        normalized_email = email.lower().strip()
        user_name = name.strip() if name else normalized_email.split("@")[0]

        if self.mongo_db is not None:
            existing = self.mongo_db["users"].find_one({"email": normalized_email})
            if existing:
                return None
            doc = {
                "id": str(uuid.uuid4()),
                "email": normalized_email,
                "name": user_name,
                "password_hash": hash_password(password),
                "is_verified": True,
                "email_subscribed": email_subscribed,
                "created_at": datetime.utcnow(),
                "last_login": datetime.utcnow()
            }
            self.mongo_db["users"].insert_one(doc)
            return MongoEntity(doc)

        existing = self.session.query(User).filter_by(email=normalized_email).first()
        if existing:
            return None
        user = User(
            id=str(uuid.uuid4()),
            email=normalized_email,
            name=user_name,
            password_hash=hash_password(password),
            is_verified=True,
            email_subscribed=email_subscribed,
            created_at=datetime.utcnow(),
            last_login=datetime.utcnow()
        )
        self.session.add(user)
        self.session.commit()
        return user

    def authenticate_user(self, email: str, password: str):
        normalized_email = email.lower().strip()
        if self.mongo_db is not None:
            doc = self.mongo_db["users"].find_one({"email": normalized_email})
            if not doc:
                return None
            if verify_password(doc.get("password_hash", ""), password):
                now = datetime.utcnow()
                self.mongo_db["users"].update_one({"email": normalized_email}, {"$set": {"last_login": now}})
                doc["last_login"] = now
                return MongoEntity(doc)
            return None

        user = self.session.query(User).filter_by(email=normalized_email).first()
        if not user:
            return None
        if verify_password(user.password_hash, password):
            user.last_login = datetime.utcnow()
            self.session.commit()
            return user
        return None

    def get_user_by_email(self, email: str):
        normalized_email = email.lower().strip()
        if self.mongo_db is not None:
            doc = self.mongo_db["users"].find_one({"email": normalized_email})
            return MongoEntity(doc) if doc else None
        return self.session.query(User).filter_by(email=normalized_email).first()

    def get_user_by_id(self, user_id: str):
        if self.mongo_db is not None:
            doc = self.mongo_db["users"].find_one({"id": user_id})
            return MongoEntity(doc) if doc else None
        return self.session.query(User).filter_by(id=user_id).first()

    def update_user_subscription(self, user_id: str, subscribed: bool) -> bool:
        if self.mongo_db is not None:
            res = self.mongo_db["users"].update_one({"id": user_id}, {"$set": {"email_subscribed": subscribed}})
            return res.modified_count > 0
        user = self.get_user_by_id(user_id)
        if user:
            user.email_subscribed = subscribed
            self.session.commit()
            return True
        return False

    def get_subscribed_users(self):
        if self.mongo_db is not None:
            cursor = self.mongo_db["users"].find({"email_subscribed": True})
            return [MongoEntity(d) for d in cursor]
        return self.session.query(User).filter_by(email_subscribed=True).all()

    def get_all_subscribers_admin(self) -> List[Dict[str, Any]]:
        """Returns all subscribers with active status and created timestamps for founder admin."""
        results = []
        seen = set()
        if self.mongo_db is not None:
            for s in self.mongo_db["subscribers"].find({}).sort("created_at", -1):
                em = (s.get("email") or "").strip().lower()
                if em and em not in seen:
                    seen.add(em)
                    dt = s.get("created_at")
                    dt_str = dt.strftime("%Y-%m-%d %H:%M") if hasattr(dt, "strftime") else str(dt or "")
                    results.append({
                        "id": str(s.get("id") or s.get("_id", "")),
                        "email": em,
                        "is_active": s.get("is_active", True),
                        "created_at": dt_str
                    })
            for u in self.mongo_db["users"].find({}).sort("created_at", -1):
                em = (u.get("email") or "").strip().lower()
                if em and em not in seen:
                    seen.add(em)
                    dt = u.get("created_at")
                    dt_str = dt.strftime("%Y-%m-%d %H:%M") if hasattr(dt, "strftime") else str(dt or "")
                    results.append({
                        "id": str(u.get("id") or u.get("_id", "")),
                        "email": em,
                        "is_active": u.get("email_subscribed", True),
                        "created_at": dt_str
                    })
            return results

        # SQL fallback
        subs = self.session.query(Subscriber).order_by(Subscriber.created_at.desc()).all()
        for s in subs:
            em = s.email.strip().lower()
            if em not in seen:
                seen.add(em)
                results.append({
                    "id": s.id,
                    "email": em,
                    "is_active": s.is_active,
                    "created_at": s.created_at.strftime("%Y-%m-%d %H:%M") if s.created_at else ""
                })
        users = self.session.query(User).order_by(User.created_at.desc()).all()
        for u in users:
            em = u.email.strip().lower()
            if em not in seen:
                seen.add(em)
                results.append({
                    "id": u.id,
                    "email": em,
                    "is_active": u.email_subscribed,
                    "created_at": u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else ""
                })
        return results

    # ---------------- Direct Newsletter Subscribers ----------------
    def subscribe_email(self, email: str) -> Dict[str, Any]:
        normalized_email = email.lower().strip()
        now = datetime.now(timezone.utc)
        
        if self.mongo_db is not None:
            existing = self.mongo_db["subscribers"].find_one({"email": normalized_email})
            if existing:
                if not existing.get("is_active", True):
                    self.mongo_db["subscribers"].update_one(
                        {"email": normalized_email},
                        {"$set": {"is_active": True, "updated_at": now}}
                    )
                    return {"success": True, "created": False, "reactivated": True, "already_subscribed": False, "email": normalized_email}
                return {"success": True, "created": False, "reactivated": False, "already_subscribed": True, "email": normalized_email}

            doc = {
                "id": str(uuid.uuid4()),
                "email": normalized_email,
                "is_active": True,
                "created_at": now
            }
            self.mongo_db["subscribers"].insert_one(doc)
            return {"success": True, "created": True, "reactivated": False, "already_subscribed": False, "email": normalized_email}

        # SQL fallback
        sub = self.session.query(Subscriber).filter_by(email=normalized_email).first()
        if sub:
            if not sub.is_active:
                sub.is_active = True
                self.session.commit()
                return {"success": True, "created": False, "reactivated": True, "already_subscribed": False, "email": normalized_email}
            return {"success": True, "created": False, "reactivated": False, "already_subscribed": True, "email": normalized_email}

        new_sub = Subscriber(
            id=str(uuid.uuid4()),
            email=normalized_email,
            is_active=True,
            created_at=now
        )
        self.session.add(new_sub)
        self.session.commit()
        return {"success": True, "created": True, "reactivated": False, "already_subscribed": False, "email": normalized_email}

    def get_all_subscriber_emails(self) -> List[str]:
        emails = set()
        if self.mongo_db is not None:
            for s in self.mongo_db["subscribers"].find({"is_active": True}):
                if s.get("email"):
                    emails.add(s["email"].strip().lower())
            for u in self.mongo_db["users"].find({"email_subscribed": True}):
                if u.get("email"):
                    emails.add(u["email"].strip().lower())
            return sorted(list(emails))

        # SQL fallback
        subs = self.session.query(Subscriber).filter_by(is_active=True).all()
        for s in subs:
            if s.email:
                emails.add(s.email.strip().lower())
        users = self.session.query(User).filter_by(email_subscribed=True).all()
        for u in users:
            if u.email:
                emails.add(u.email.strip().lower())
        return sorted(list(emails))

    def get_subscribers_count(self) -> int:
        return len(self.get_all_subscriber_emails())

    def unsubscribe_email(self, email: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Unsubscribes a user from the newsletter.
        Marks is_active=False in subscribers and email_subscribed=False in users.
        Retains the record in the database and records in unsubscribers list for audit.
        """
        normalized_email = email.lower().strip()
        now = datetime.now(timezone.utc)
        found = False

        if self.mongo_db is not None:
            # Check subscribers collection
            sub = self.mongo_db["subscribers"].find_one({"email": normalized_email})
            if sub:
                self.mongo_db["subscribers"].update_one(
                    {"email": normalized_email},
                    {"$set": {
                        "is_active": False,
                        "unsubscribed_at": now,
                        "unsubscribe_reason": reason or "User requested unsubscribe"
                    }}
                )
                found = True
            else:
                self.mongo_db["subscribers"].insert_one({
                    "id": str(uuid.uuid4()),
                    "email": normalized_email,
                    "is_active": False,
                    "unsubscribed_at": now,
                    "unsubscribe_reason": reason or "User requested unsubscribe"
                })
                found = True

            # Also check users collection
            self.mongo_db["users"].update_many(
                {"email": normalized_email},
                {"$set": {"email_subscribed": False}}
            )

            # Record in dedicated unsubscribers audit collection
            self.mongo_db["unsubscribers"].update_one(
                {"email": normalized_email},
                {"$set": {
                    "email": normalized_email,
                    "unsubscribed_at": now,
                    "reason": reason or "User requested unsubscribe"
                }},
                upsert=True
            )
            return {"success": True, "found": found, "email": normalized_email}

        # SQL fallback
        sub = self.session.query(Subscriber).filter_by(email=normalized_email).first()
        if sub:
            sub.is_active = False
            self.session.commit()
            found = True
        user = self.session.query(User).filter_by(email=normalized_email).first()
        if user:
            user.email_subscribed = False
            self.session.commit()
            found = True
        return {"success": True, "found": found, "email": normalized_email}

    def get_unsubscribers(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Returns list of unsubscribed emails from MongoDB for audit."""
        if self.mongo_db is not None:
            unsubs = list(
                self.mongo_db["subscribers"]
                .find({"is_active": False}, {"_id": 0})
                .sort("unsubscribed_at", -1)
                .limit(limit)
            )
            return unsubs
        return []

    # ---------------- Reviews & Feedback ----------------
    def add_review(
        self,
        name: str,
        email: str,
        comment: str,
        rating: int = 5,
        role: Optional[str] = None,
        is_public: bool = True,
        is_approved: bool = True
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        clean_email = email.strip().lower() if email else ""
        review_id = str(uuid.uuid4())
        doc = {
            "id": review_id,
            "name": name.strip(),
            "email": clean_email,
            "role": (role or "Community Member").strip(),
            "rating": max(1, min(5, int(rating))),
            "comment": comment.strip(),
            "is_public": bool(is_public),
            "is_approved": bool(is_approved),
            "created_at": now.strftime("%b %d, %Y"),
            "timestamp": now.isoformat()
        }
        if self.mongo_db is not None:
            self.mongo_db["reviews"].insert_one(dict(doc))
            doc.pop("_id", None)
            return doc

        # Fallback SQL persistence
        try:
            sql_rev = Review(
                id=review_id,
                name=doc["name"],
                email=clean_email,
                role=doc["role"],
                rating=str(doc["rating"]),
                comment=doc["comment"],
                is_public=doc["is_public"],
                is_approved=doc["is_approved"],
                created_at=now,
                timestamp=doc["timestamp"]
            )
            self.session.add(sql_rev)
            self.session.commit()
        except Exception as e:
            logger.warning(f"Failed to persist review in SQL fallback: {e}")
            self.session.rollback()

        return doc

    def get_reviews(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Returns only real, approved public reviews.
        Strictly excludes reviewer emails for privacy.
        Never returns or seeds fake reviews.
        """
        if self.mongo_db is not None:
            try:
                # Only return approved and public reviews, strictly hiding reviewer emails
                query = {
                    "$and": [
                        {"is_approved": True},
                        {"$or": [{"is_public": True}, {"is_public": {"$exists": False}}]}
                    ]
                }
                reviews = list(
                    self.mongo_db["reviews"]
                    .find(query, {"_id": 0, "email": 0})
                    .sort("timestamp", -1)
                    .limit(limit)
                )
                return reviews or []
            except Exception as e:
                logger.warning(f"Error reading reviews from MongoDB: {e}")
                return []

        # SQL fallback
        try:
            rows = (
                self.session.query(Review)
                .filter(Review.is_approved == True, Review.is_public == True)
                .order_by(Review.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": r.id,
                    "name": r.name,
                    "role": r.role,
                    "rating": int(r.rating) if r.rating and str(r.rating).isdigit() else 5,
                    "comment": r.comment,
                    "is_public": r.is_public,
                    "is_approved": r.is_approved,
                    "created_at": r.created_at.strftime("%b %d, %Y") if r.created_at else "",
                    "timestamp": r.timestamp or (r.created_at.isoformat() if r.created_at else "")
                }
                for r in rows
            ]
        except Exception as e:
            logger.warning(f"Error fetching reviews from SQL: {e}")
            return []

    def get_all_reviews_admin(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Returns all reviews including pending/moderated and private ones for founder review."""
        if self.mongo_db is not None:
            try:
                reviews = list(self.mongo_db["reviews"].find({}, {"_id": 0}).sort("timestamp", -1).limit(limit))
                return reviews or []
            except Exception as e:
                logger.warning(f"Error fetching admin reviews: {e}")
                return []
        try:
            rows = self.session.query(Review).order_by(Review.created_at.desc()).limit(limit).all()
            return [
                {
                    "id": r.id,
                    "name": r.name,
                    "email": r.email,
                    "role": r.role,
                    "rating": int(r.rating) if r.rating and str(r.rating).isdigit() else 5,
                    "comment": r.comment,
                    "is_public": r.is_public,
                    "is_approved": r.is_approved,
                    "created_at": r.created_at.strftime("%b %d, %Y") if r.created_at else "",
                    "timestamp": r.timestamp or ""
                }
                for r in rows
            ]
        except Exception:
            return []

    def delete_review(self, review_id: str) -> bool:
        """Deletes a review by its ID from MongoDB or SQL."""
        if self.mongo_db is not None:
            res = self.mongo_db["reviews"].delete_one({"id": review_id})
            return res.deleted_count > 0
        try:
            row = self.session.query(Review).filter_by(id=review_id).first()
            if row:
                self.session.delete(row)
                self.session.commit()
                return True
        except Exception:
            self.session.rollback()
        return False

    # ---------------- Email Dispatch Telemetry ----------------
    def log_email_dispatch(self, recipient: str, subject: str, email_type: str, success: bool, error: Optional[str] = None) -> None:
        """Stores email dispatch audit log in MongoDB Atlas for instant diagnostics."""
        if self.mongo_db is not None:
            try:
                now = datetime.now(timezone.utc)
                doc = {
                    "id": str(uuid.uuid4()),
                    "recipient": recipient.strip().lower(),
                    "subject": subject,
                    "email_type": email_type,
                    "success": bool(success),
                    "error": str(error) if error else None,
                    "timestamp": now.isoformat(),
                    "formatted_time": now.strftime("%b %d, %Y %H:%M:%S UTC")
                }
                self.mongo_db["email_logs"].insert_one(doc)
            except Exception as e:
                logger.warning(f"Failed to record email log in MongoDB: {e}")

    def get_email_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves recent email audit logs from MongoDB Atlas."""
        if self.mongo_db is not None:
            try:
                return list(
                    self.mongo_db["email_logs"]
                    .find({}, {"_id": 0})
                    .sort("timestamp", -1)
                    .limit(limit)
                )
            except Exception as e:
                logger.warning(f"Failed to fetch email logs: {e}")
                return []
        return []

