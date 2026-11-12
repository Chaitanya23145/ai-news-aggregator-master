import os
import json
import logging
from typing import List
from groq import Groq
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class RankedArticle(BaseModel):
    digest_id: str = Field(description="The ID of the digest (article_type:article_id)")
    relevance_score: float = Field(description="Relevance score from 0.0 to 10.0", ge=0.0, le=10.0)
    rank: int = Field(description="Rank position (1 = most relevant)", ge=1)
    reasoning: str = Field(description="Brief explanation of why this article is ranked here")


class RankedDigestList(BaseModel):
    articles: List[RankedArticle] = Field(description="List of ranked articles")


CURATOR_PROMPT = """You are an expert AI news curator specializing in personalized content ranking for AI professionals.

Your role is to analyze and rank AI-related news articles, research papers, and video content based on a user's specific profile, interests, and background.

Ranking Criteria:
1. Relevance to user's stated interests and background
2. Technical depth and practical value
3. Novelty and significance of the content
4. Alignment with user's expertise level
5. Actionability and real-world applicability

Scoring Guidelines:
- 9.0-10.0: Highly relevant, directly aligns with user interests, significant value
- 7.0-8.9: Very relevant, strong alignment with interests, good value
- 5.0-6.9: Moderately relevant, some alignment, decent value
- 3.0-4.9: Somewhat relevant, limited alignment, lower value
- 0.0-2.9: Low relevance, minimal alignment, little value

Rank articles from most relevant (rank 1) to least relevant. Ensure each article has a unique rank.

You MUST respond with valid JSON in this exact format:
{"articles": [{"digest_id": "type:id", "relevance_score": 8.5, "rank": 1, "reasoning": "explanation"}]}"""


class CuratorAgent:
    def __init__(self, user_profile: dict):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.client = None
        if self.api_key:
            try:
                self.client = Groq(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Groq curator client init notice: {e}")
                self.client = None
        self.model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        self.user_profile = user_profile
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        interests = "\n".join(f"- {interest}" for interest in self.user_profile["interests"])
        preferences = self.user_profile["preferences"]
        pref_text = "\n".join(f"- {k}: {v}" for k, v in preferences.items())
        
        return f"""{CURATOR_PROMPT}

User Profile:
Name: {self.user_profile["name"]}
Background: {self.user_profile["background"]}
Expertise Level: {self.user_profile["expertise_level"]}

Interests:
{interests}

Preferences:
{pref_text}"""

    def rank_digests(self, digests: List[dict]) -> List[RankedArticle]:
        if not digests:
            return []
        
        digest_list = "\n\n".join([
            f"ID: {d['id']}\nTitle: {d['title']}\nSummary: {d['summary']}\nType: {d['article_type']}"
            for d in digests
        ])
        
        user_prompt = f"""Rank these {len(digests)} AI news digests based on the user profile:

{digest_list}

Provide a relevance score (0.0-10.0) and rank (1-{len(digests)}) for each article, ordered from most to least relevant."""

        # 1. Primary AI Ranking
        if self.client:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3,
                    response_format={"type": "json_object"}
                )
                
                result = json.loads(response.choices[0].message.content)
                ranked_list = RankedDigestList(**result)
                if ranked_list and ranked_list.articles:
                    return ranked_list.articles
            except Exception as e:
                logger.warning(
                    f"⚠️ [Curator AI Failed / Tokens Depleted] ({e}). "
                    f"Activating autonomous heuristic fallback ranker for {len(digests)} articles..."
                )
        else:
            logger.info(
                f"ℹ️ [Curator Client Offline] Activating autonomous heuristic fallback ranker for {len(digests)} articles..."
            )

        # 2. Heuristic Backup Ranking (ONLY runs when AI fails)
        return self._heuristic_fallback_ranking(digests)

    def _heuristic_fallback_ranking(self, digests: List[dict]) -> List[RankedArticle]:
        """
        Autonomous heuristic fallback ranker when Groq tokens are depleted or API is down.
        Ranks digests based on keyword affinity with user profile interests and domain novelty.
        """
        interests = [i.lower() for i in self.user_profile.get("interests", [])]
        scored_items = []

        for d in digests:
            text = f"{d.get('title', '')} {d.get('summary', '')}".lower()
            score = 7.5
            matched = []
            for interest in interests:
                if interest in text:
                    score += 0.8
                    matched.append(interest)
            
            # Bonus for source diversity
            art_type = d.get("article_type", "").lower()
            if art_type in ["arxiv", "anthropic", "openai"]:
                score += 0.5
            
            final_score = min(9.9, round(score, 1))
            reason = (
                f"Autonomous heuristic match: aligns with user focus in {', '.join(matched)}."
                if matched
                else "Autonomous heuristic match: high-value technical intelligence update."
            )
            scored_items.append((final_score, reason, d))

        # Sort descending by relevance score
        scored_items.sort(key=lambda x: x[0], reverse=True)
        
        ranked_articles = []
        for idx, (score, reason, d) in enumerate(scored_items, 1):
            ranked_articles.append(RankedArticle(
                digest_id=d["id"],
                relevance_score=score,
                rank=idx,
                reasoning=reason
            ))

        logger.info(f"✓ [Backup Ranker] Successfully ranked {len(ranked_articles)} articles.")
        return ranked_articles
