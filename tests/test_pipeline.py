"""
==========================================================
AI News Aggregator - Unit & Integration Test Suite
Author : Chaitanya Upadhyay
==========================================================
"""

import unittest
import os
from datetime import datetime, timezone
from app.config import RSS_FEEDS, GROQ_MODEL, DEFAULT_HOURS
from app.scrapers.huggingface import HuggingFaceArticle
from app.scrapers.techcrunch import TechCrunchArticle
from app.scrapers.arxiv_ai import ArxivArticle
from app.services.digest_exporter import DigestExporter
from app.database.connection import get_database_url
from app.services.webhook_alerts import WebhookAlertService
from app.services.vector_clustering import VectorClusteringService, generate_text_embedding, cosine_similarity
from app.profiles.preference_manager import PreferenceManager


class TestConfiguration(unittest.TestCase):
    def test_rss_feeds_present(self):
        self.assertIn("openai", RSS_FEEDS)
        self.assertIn("anthropic", RSS_FEEDS)
        self.assertIn("huggingface", RSS_FEEDS)
        self.assertIn("techcrunch_ai", RSS_FEEDS)
        self.assertIn("arxiv_ai", RSS_FEEDS)

    def test_default_settings(self):
        self.assertGreater(DEFAULT_HOURS, 0)
        self.assertTrue(len(GROQ_MODEL) > 0)


class TestScraperModels(unittest.TestCase):
    def test_huggingface_model(self):
        now = datetime.now(timezone.utc)
        article = HuggingFaceArticle(
            guid="hf-1",
            title="SmolLM2 Released",
            url="https://huggingface.co/blog/smollm2",
            published_at=now,
            description="A lightweight on-device LLM model.",
            category="HuggingFace"
        )
        self.assertEqual(article.title, "SmolLM2 Released")
        self.assertEqual(article.category, "HuggingFace")

    def test_techcrunch_model(self):
        now = datetime.now(timezone.utc)
        article = TechCrunchArticle(
            guid="tc-1",
            title="New AI Funding Round",
            url="https://techcrunch.com/article",
            published_at=now,
            description="Major AI startup closes round.",
            category="TechCrunch AI"
        )
        self.assertEqual(article.title, "New AI Funding Round")

    def test_arxiv_model(self):
        now = datetime.now(timezone.utc)
        paper = ArxivArticle(
            guid="arxiv-1",
            title="Attention is Still All You Need",
            url="https://arxiv.org/abs/2401.00000",
            published_at=now,
            description="Survey on transformer scaling laws.",
            category="arXiv AI"
        )
        self.assertEqual(paper.category, "arXiv AI")


class TestWebhookAlerts(unittest.TestCase):
    def test_alert_threshold(self):
        svc = WebhookAlertService(min_score=8.0)
        self.assertTrue(svc.should_alert(8.5))
        self.assertTrue(svc.should_alert(9.0))
        self.assertFalse(svc.should_alert(7.5))

    def test_empty_webhook_graceful(self):
        svc = WebhookAlertService(slack_url="", discord_url="")
        res = svc.dispatch_alert("Test Title", "Test Summary", "http://test.com", relevance_score=9.5)
        self.assertFalse(res["slack_sent"])
        self.assertFalse(res["discord_sent"])


class TestVectorClustering(unittest.TestCase):
    def test_embedding_and_cosine_similarity(self):
        v1 = generate_text_embedding("large language model transformer reasoning")
        v2 = generate_text_embedding("large language model deep neural transformer")
        v3 = generate_text_embedding("gardening soil plant flowers sunlight")

        sim_related = cosine_similarity(v1, v2)
        sim_unrelated = cosine_similarity(v1, v3)

        self.assertGreater(sim_related, sim_unrelated)
        self.assertGreater(sim_related, 0.4)

    def test_clustering_grouping(self):
        svc = VectorClusteringService(similarity_threshold=0.35)
        articles = [
            {"title": "OpenAI releases o3 reasoning model", "summary": "o3 reasoning benchmark breakthroughs", "article_type": "openai"},
            {"title": "Anthropic unveils Claude 3.5 Sonnet", "summary": "Coding and reasoning improvements in Claude", "article_type": "anthropic"},
            {"title": "Quantum computing advances in superconducting qubits", "summary": "Hardware qubit fidelity reaches 99.9%", "article_type": "techcrunch"},
        ]
        clusters = svc.cluster_articles(articles)
        self.assertGreater(len(clusters), 0)


class TestPreferenceManager(unittest.TestCase):
    def test_preferences_load_and_update(self):
        test_file = "tests/test_prefs.json"
        mgr = PreferenceManager(filepath=test_file)
        prefs = mgr.get_preferences()
        self.assertIn("preferred_topics", prefs)

        updated = mgr.update_preferences({"technical_depth_weight": 4.5})
        self.assertEqual(updated["technical_depth_weight"], 4.5)

        if os.path.exists(test_file):
            os.remove(test_file)


class TestDigestExporter(unittest.TestCase):
    def test_export_digest(self):
        exporter = DigestExporter(output_dir="tests/test_output")

        class MockDigestResult:
            def to_markdown(self):
                return "# Daily AI News Digest\n\n- **OpenAI GPT-5**: Major breakthroughs announced."

        mock_res = MockDigestResult()
        export_info = exporter.export_digest(mock_res, date_str="2026-09-14")

        self.assertTrue(os.path.exists(export_info["markdown_path"]))
        with open(export_info["markdown_path"], "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Daily AI News Digest", content)

        # Clean up
        if os.path.exists(export_info["markdown_path"]):
            os.remove(export_info["markdown_path"])
        if os.path.exists(export_info["latest_path"]):
            os.remove(export_info["latest_path"])
        if os.path.exists("tests/test_output"):
            try:
                os.rmdir("tests/test_output")
            except OSError:
                pass


class TestDatabaseConnection(unittest.TestCase):
    def setUp(self):
        from app.database.connection import Base, engine
        try:
            Base.metadata.create_all(bind=engine)
        except Exception:
            pass

    def test_database_url_fallback(self):
        url = get_database_url()
        self.assertTrue(url.startswith("sqlite://") or url.startswith("postgresql://"))

    def test_user_authentication_flow(self):
        from app.database.repository import Repository
        repo = Repository()
        test_email = "ci_test_user@example.com"
        
        # Create user
        user = repo.create_user(test_email, "securepass123", "CI User")
        self.assertIsNotNone(user)
        self.assertEqual(user.email, test_email)

        # Authenticate with correct password
        auth_success = repo.authenticate_user(test_email, "securepass123")
        self.assertIsNotNone(auth_success)

        # Authenticate with incorrect password
        auth_fail = repo.authenticate_user(test_email, "wrongpassword")
        self.assertIsNone(auth_fail)

        # Cleanup
        if repo.mongo_db is not None:
            repo.mongo_db["users"].delete_one({"email": test_email})
        elif repo.session is not None:
            from app.database.models import User
            repo.session.query(User).filter_by(email=test_email).delete()
            repo.session.commit()


class TestAutonomousBackupSummarizer(unittest.TestCase):
    def test_algorithmic_backup_summarization_on_ai_failure(self):
        from app.agent.digest_agent import DigestAgent
        agent = DigestAgent()
        
        # Force client to None to simulate token depletion / API downtime
        agent.client = None
        
        title = "DeepSeek-V3 Technical Report: Multi-Head Latent Attention and 671B Parameter MoE Architecture"
        content = (
            "DeepSeek introduces DeepSeek-V3, a strong Mixture-of-Experts language model with 671B total parameters "
            "and 37B activated per token. The architecture employs Multi-Head Latent Attention (MLA) to compress KV cache "
            "and achieve superior inference efficiency. Extensive evaluations across MMLU, GSM8K, and HumanEval demonstrate "
            "that DeepSeek-V3 outperforms leading open models while cutting training compute significantly. "
            "Click here to subscribe for more news and updates."
        )
        
        result = agent.generate_digest(title=title, content=content, article_type="arxiv")
        
        self.assertIsNotNone(result)
        self.assertTrue(result.is_backup)
        self.assertTrue(len(result.summary) > 40)
        self.assertIn("DeepSeek", result.summary)
        # Verify marketing boilerplate was filtered out
        self.assertNotIn("Click here to subscribe", result.summary)

    def test_curator_heuristic_fallback_ranking(self):
        from app.agent.curator_agent import CuratorAgent
        from app.profiles.user_profile import USER_PROFILE
        curator = CuratorAgent(USER_PROFILE)
        
        # Force client to None to simulate token depletion / API downtime
        curator.client = None
        
        digests = [
            {"id": "arxiv:1", "title": "Scaling Test-Time Compute in LLM Reasoning", "summary": "Study on reasoning tokens and RL verification.", "article_type": "arxiv"},
            {"id": "tc:2", "title": "Venture Capital in Silicon Valley", "summary": "Investment rounds in enterprise SaaS.", "article_type": "techcrunch"},
            {"id": "openai:3", "title": "OpenAI Introduces o3 Frontier Model", "summary": "Breakthrough benchmarks on math Olympiads.", "article_type": "openai"}
        ]
        
        ranked = curator.rank_digests(digests)
        self.assertEqual(len(ranked), 3)
        self.assertEqual(ranked[0].rank, 1)
        self.assertTrue(ranked[0].relevance_score >= ranked[1].relevance_score)
        self.assertIn("Autonomous heuristic match", ranked[0].reasoning)


class TestEmailValidation(unittest.TestCase):
    def test_email_validator_rules(self):
        from app.services.email_validator import validate_email_address
        
        # Valid email
        ok, msg = validate_email_address("chaitanya23145@gmail.com")
        self.assertTrue(ok)

        # Disposable domain blocked
        ok, msg = validate_email_address("burner@mailinator.com")
        self.assertFalse(ok)
        self.assertIn("disposable", msg.lower())

        # Domain typo detected
        ok, msg = validate_email_address("coder@gamil.com")
        self.assertFalse(ok)
        self.assertIn("@gmail.com", msg)

        # Non-existent domain blocked via DNS
        ok, msg = validate_email_address("user@thisdomaindoesnotexist999888777.com")
        self.assertFalse(ok)
        self.assertTrue("does not exist" in msg or "cannot receive" in msg)

        # Malformed syntax blocked
        ok, msg = validate_email_address("invalid..email@domain.com")
        self.assertFalse(ok)


class TestSubscriptionAndReviewPersistence(unittest.TestCase):
    def test_already_subscribed_detection(self):
        from app.database.repository import Repository
        import uuid
        repo = Repository()
        test_email = f"tester_{uuid.uuid4().hex[:8]}@example.com"

        # First subscription should succeed and set created = True
        res1 = repo.subscribe_email(test_email)
        self.assertTrue(res1.get("success"))
        self.assertTrue(res1.get("created"))
        self.assertFalse(res1.get("already_subscribed"))

        # Second subscription with same email must indicate already_subscribed = True
        res2 = repo.subscribe_email(test_email)
        self.assertTrue(res2.get("success"))
        self.assertFalse(res2.get("created"))
        self.assertTrue(res2.get("already_subscribed"))

        # Clean up test subscriber
        if repo.mongo_db is not None:
            repo.mongo_db["subscribers"].delete_one({"email": test_email.lower().strip()})

    def test_review_persistence_and_privacy(self):
        from app.database.repository import Repository
        import uuid
        repo = Repository()
        unique_name = f"Researcher_{uuid.uuid4().hex[:6]}"
        unique_comment = "High quality synthesis of frontier models."

        # Add review to repository
        review = repo.add_review(
            name=unique_name,
            email="author@example.com",
            comment=unique_comment,
            rating=5,
            role="Research Fellow",
            is_public=True,
            is_approved=True
        )
        self.assertIsNotNone(review.get("id"))
        self.assertEqual(review.get("name"), unique_name)

        # Retrieve reviews from DB
        reviews = repo.get_reviews(limit=50)
        found = next((r for r in reviews if r.get("id") == review["id"]), None)
        self.assertIsNotNone(found, "Saved review must be found in database queries")
        self.assertEqual(found["name"], unique_name)
        # Ensure reviewer email is never exposed in public query
        self.assertNotIn("email", found)

        # Clean up
        if repo.mongo_db is not None:
            repo.mongo_db["reviews"].delete_one({"id": review["id"]})


class TestNewFeaturesAndSeo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ensure SQLite tables exist before API tests (needed when MongoDB is unavailable in CI)
        from app.database.connection import Base, engine, init_db
        Base.metadata.create_all(bind=engine)
        init_db()
        from fastapi.testclient import TestClient
        from app.api import app
        cls.client = TestClient(app)

    def test_rss_feed_generation(self):
        res = self.client.get("/rss")
        self.assertEqual(res.status_code, 200)
        self.assertIn("application/rss+xml", res.headers.get("content-type", ""))
        self.assertIn("<rss version=\"2.0\"", res.text)
        self.assertIn("<title>Synapse AI", res.text)

    def test_robots_and_sitemap(self):
        robots = self.client.get("/robots.txt")
        self.assertEqual(robots.status_code, 200)
        self.assertIn("User-agent: *", robots.text)
        self.assertIn("Sitemap:", robots.text)

        sitemap = self.client.get("/sitemap.xml")
        self.assertEqual(sitemap.status_code, 200)
        self.assertIn("<urlset", sitemap.text)

    def test_admin_route_removed(self):
        res = self.client.get("/admin")
        self.assertEqual(res.status_code, 404)

    def test_honeypot_trap(self):
        # When bot fills honeypot field, it should return benign success without creating subscriber
        res = self.client.post("/api/subscribe", json={
            "email": "bot@spam-crawler.com",
            "website_hp": "http://spamsite.xyz"
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get("status"), "success")


if __name__ == "__main__":
    unittest.main()
