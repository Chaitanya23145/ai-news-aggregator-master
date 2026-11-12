import os
import json
from datetime import datetime
from typing import List, Optional
from groq import Groq
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()


class EmailIntroduction(BaseModel):
    greeting: str = Field(description="Personalized greeting with user's name and date")
    introduction: str = Field(description="2-3 sentence overview of what's in the top 10 ranked articles")


class RankedArticleDetail(BaseModel):
    digest_id: str
    rank: int
    relevance_score: float
    title: str
    summary: str
    url: str
    article_type: str
    reasoning: Optional[str] = None


class EmailDigestResponse(BaseModel):
    introduction: EmailIntroduction
    articles: List[RankedArticleDetail]
    total_ranked: int
    top_n: int
    
    def to_markdown(self) -> str:
        markdown = f"{self.introduction.greeting}\n\n"
        markdown += f"{self.introduction.introduction}\n\n"
        markdown += "---\n\n"
        
        for article in self.articles:
            markdown += f"## {article.title}\n\n"
            markdown += f"{article.summary}\n\n"
            markdown += f"[Read more →]({article.url})\n\n"
            markdown += "---\n\n"
        
        return markdown


class EmailDigest(BaseModel):
    introduction: EmailIntroduction
    ranked_articles: List[dict] = Field(description="Top 10 ranked articles with their details")


EMAIL_PROMPT = """You are an expert email writer specializing in creating engaging, personalized AI news digests.

Your role is to write a warm, professional introduction for a daily AI news digest email that:
- Greets the user by name
- Includes the current date
- Provides a brief, engaging overview of what's coming in the top 10 ranked articles
- Highlights the most interesting or important themes
- Sets expectations for the content ahead

Keep it concise (2-3 sentences for the introduction), friendly, and professional.

You MUST respond with valid JSON in this exact format:
{"greeting": "your greeting here", "introduction": "your introduction here"}"""


class EmailAgent:
    def __init__(self, user_profile: dict):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        raw_model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        self.model = "openai/gpt-oss-120b" if ("llama" in raw_model.lower() or not raw_model.strip()) else raw_model
        self.user_profile = user_profile

    def generate_introduction(self, ranked_articles: List) -> EmailIntroduction:
        current_date = datetime.now().strftime('%B %d, %Y')
        default_greeting = f"Good morning! Here is your daily frontier AI briefing for {current_date}."
        default_intro = "Here are today's top curated AI breakthroughs, model releases, and research developments, analyzed and ranked for technical impact."

        if not ranked_articles:
            return EmailIntroduction(
                greeting=default_greeting,
                introduction="No articles were ranked today."
            )
        
        top_articles = ranked_articles[:10]
        article_summaries = "\n".join([
            f"{idx + 1}. {article.title if hasattr(article, 'title') else article.get('title', 'N/A')} (Score: {article.relevance_score if hasattr(article, 'relevance_score') else article.get('relevance_score', 0):.1f}/10)"
            for idx, article in enumerate(top_articles)
        ])
        
        user_prompt = f"""Create an executive email briefing introduction for {current_date}.

Top 10 ranked articles:
{article_summaries}

Generate a compelling, professional greeting and an executive 2-sentence preview highlighting the most important breakthroughs today."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": EMAIL_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            intro = EmailIntroduction(**result)
            # Remove any unwanted legacy placeholder names like "Dave"
            if "dave" in intro.greeting.lower():
                intro.greeting = default_greeting
            
            return intro
        except Exception as e:
            print(f"Error generating introduction: {e}")
            return EmailIntroduction(
                greeting=default_greeting,
                introduction=default_intro
            )

    def create_email_digest(self, ranked_articles: List[dict], limit: int = 10) -> EmailDigest:
        top_articles = ranked_articles[:limit]
        introduction = self.generate_introduction(top_articles)
        
        return EmailDigest(
            introduction=introduction,
            ranked_articles=top_articles
        )
    
    def create_email_digest_response(self, ranked_articles: List[RankedArticleDetail], total_ranked: int, limit: int = 10) -> EmailDigestResponse:
        top_articles = ranked_articles[:limit]
        introduction = self.generate_introduction(top_articles)
        
        return EmailDigestResponse(
            introduction=introduction,
            articles=top_articles,
            total_ranked=total_ranked,
            top_n=limit
        )
