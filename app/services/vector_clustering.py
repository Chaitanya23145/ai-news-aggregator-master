"""
==========================================================
AI News Aggregator - Vector Similarity & Semantic Clustering
Semantic clustering, deduplication, and pgvector integration
Author : Chaitanya Upadhyay
==========================================================
"""

import math
import re
from typing import List, Dict, Any, Tuple, Optional
from collections import Counter


def tokenize(text: str) -> List[str]:
    """Extracts alphanumeric normalized tokens from text."""
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    stop_words = {
        "the", "and", "for", "with", "this", "that", "from", "are", "was", "were",
        "will", "have", "has", "had", "can", "could", "should", "about", "into", "more"
    }
    return [w for w in words if w not in stop_words]


def generate_text_embedding(text: str, dim: int = 128) -> List[float]:
    """
    Generates a normalized deterministic dense vector embedding [dim-length]
    via feature hashing and term frequency. Works offline without external weights.
    """
    tokens = tokenize(text)
    if not tokens:
        return [0.0] * dim

    vec = [0.0] * dim
    counts = Counter(tokens)
    for token, count in counts.items():
        # Hash token into vector dimension index
        idx = hash(token) % dim
        vec[idx] += float(count)

    # Normalize vector to unit length (L2 norm)
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [round(x / norm, 5) for x in vec]
    return vec


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calculates cosine similarity between two normalized vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


class SemanticCluster:
    def __init__(self, cluster_id: int, topic: str):
        self.cluster_id = cluster_id
        self.topic = topic
        self.articles: List[Dict[str, Any]] = []

    def add_article(self, article: Dict[str, Any]):
        self.articles.append(article)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "topic": self.topic,
            "size": len(self.articles),
            "articles": self.articles,
        }


class VectorClusteringService:
    """
    Performs vector similarity clustering, semantic deduplication,
    and provides pgvector SQL schema generation for PostgreSQL.
    """

    def __init__(self, similarity_threshold: float = 0.60):
        self.similarity_threshold = similarity_threshold

    def is_duplicate(self, candidate_text: str, existing_texts: List[str], threshold: float = 0.88) -> bool:
        """Checks if candidate article is a duplicate of any existing articles."""
        candidate_vec = generate_text_embedding(candidate_text)
        for text in existing_texts:
            existing_vec = generate_text_embedding(text)
            sim = cosine_similarity(candidate_vec, existing_vec)
            if sim >= threshold:
                return True
        return False

    def cluster_articles(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Clusters articles based on semantic vector similarity.
        Groups related coverage across multiple scrapers into unified topic clusters.
        """
        if not articles:
            return []

        # Generate embeddings for each article
        embeddings = []
        for a in articles:
            content = f"{a.get('title', '')} {a.get('summary', '')} {a.get('description', '')}"
            embeddings.append(generate_text_embedding(content))

        assigned_cluster = [-1] * len(articles)
        clusters: List[SemanticCluster] = []
        cluster_counter = 0

        for i in range(len(articles)):
            if assigned_cluster[i] != -1:
                continue

            # Start a new cluster
            cluster_counter += 1
            tokens = tokenize(articles[i].get("title", "AI Topic"))
            topic_label = " ".join([w.capitalize() for w in tokens[:3]]) if tokens else f"AI Cluster #{cluster_counter}"
            current_cluster = SemanticCluster(cluster_id=cluster_counter, topic=topic_label)

            current_cluster.add_article(articles[i])
            assigned_cluster[i] = cluster_counter

            # Find similar articles
            for j in range(i + 1, len(articles)):
                if assigned_cluster[j] == -1:
                    sim = cosine_similarity(embeddings[i], embeddings[j])
                    if sim >= self.similarity_threshold:
                        current_cluster.add_article(articles[j])
                        assigned_cluster[j] = cluster_counter

            clusters.append(current_cluster)

        # Sort clusters by size descending
        clusters.sort(key=lambda c: len(c.articles), reverse=True)
        return [c.to_dict() for c in clusters]

    @staticmethod
    def get_pgvector_migration_sql() -> str:
        """Generates PostgreSQL DDL migration to enable pgvector extension and column."""
        return """
        -- Enable pgvector extension
        CREATE EXTENSION IF NOT EXISTS vector;

        -- Add vector embedding column to digests table (128-d or 384-d)
        ALTER TABLE digests ADD COLUMN IF NOT EXISTS embedding vector(128);

        -- Create HNSW index for ultra-fast cosine similarity search
        CREATE INDEX IF NOT EXISTS idx_digests_embedding_hnsw 
        ON digests USING hnsw (embedding vector_cosine_ops);
        """


_clustering_service = VectorClusteringService()

def get_clustering_service() -> VectorClusteringService:
    return _clustering_service
