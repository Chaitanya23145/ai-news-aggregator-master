import os
import json
import logging
import re
from typing import Optional, List
from groq import Groq
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class DigestOutput(BaseModel):
    title: str
    summary: str
    is_backup: bool = False

PROMPT = """You are an expert AI news intelligence analyst for Synapse AI.
Your role is to create insightful, high-value executive digests for frontier AI models, research papers, and industry announcements.

Guidelines:
- Title: Authoritative, compelling headline (6-12 words). Avoid clickbait.
- Summary: Write a high-density, informative 2-3 sentence summary:
  1. What was launched, discovered, or achieved (models, benchmarks, architecture, capabilities).
  2. Technical or operational significance (performance, efficiency, developer utility, or industry shift).
  3. Why this matters to engineers, researchers, and tech founders.
- If the source content is brief or a press release headline, synthesize the full context and technical meaning rather than repeating it verbatim.
- Avoid vague marketing fluff - focus on concrete value, architecture, and capabilities.

You MUST respond with valid JSON in this exact format:
{"title": "your title here", "summary": "your summary here"}"""


class DigestAgent:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.client = None
        if self.api_key:
            try:
                self.client = Groq(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Groq client initialization notice: {e}")
                self.client = None
        raw_model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        self.model = "openai/gpt-oss-120b" if ("llama" in raw_model.lower() or not raw_model.strip()) else raw_model
        self.system_prompt = PROMPT

    def generate_digest(self, title: str, content: str, article_type: str) -> DigestOutput:
        """
        Generates an executive digest for an article.
        PRIMARY: Calls Groq LLM (e.g. llama-3.3-70b-versatile) for AI synthesis.
        BACKUP: If AI fails (rate limits, zero tokens, API error, timeout, network drop),
                the autonomous algorithmic backup summarizer activates to distill
                the content into a crisp 2-3 sentence brief so the pipeline never breaks.
        """
        # 1. Attempt Primary AI Summarization
        if self.client:
            try:
                user_prompt = f"Create a digest for this {article_type}: \n Title: {title} \n Content: {content[:8000]}"

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7,
                    response_format={"type": "json_object"}
                )
                
                raw_text = response.choices[0].message.content
                result = json.loads(raw_text)
                if result.get("title") and result.get("summary"):
                    return DigestOutput(
                        title=result["title"].strip(),
                        summary=result["summary"].strip(),
                        is_backup=False
                    )
            except Exception as e:
                logger.warning(
                    f"⚠️ [AI Summarizer Failed / Tokens Depleted] ({e}). "
                    f"Activating autonomous algorithmic backup summarizer for: '{title[:45]}...'"
                )
        else:
            logger.info(
                f"ℹ️ [Groq Client Offline] Activating autonomous algorithmic backup summarizer for: '{title[:45]}...'"
            )

        # 2. Autonomous Algorithmic Backup Summarizer (ONLY runs when AI fails)
        return self._algorithmic_backup_summarize(title=title, content=content, article_type=article_type)

    def _clean_title(self, title: str) -> str:
        """Cleans source artifacts, branding tags, and trims long titles."""
        if not title:
            return "AI Research & Frontier Developments"
        # Remove HTML tags
        t = re.sub(r'<[^>]+>', '', title)
        # Remove common publication suffixes
        t = re.sub(r'\s*([|\-–—]\s*(TechCrunch|OpenAI|Anthropic|arXiv|YouTube|Hugging\s*Face|VentureBeat|The Verge)).*$', '', t, flags=re.IGNORECASE)
        # Remove arXiv ID prefixes like [2405.12345]
        t = re.sub(r'^\[\d+\.\d+\]\s*', '', t)
        t = re.sub(r'\s+', ' ', t).strip()
        # Cap to 12 words if excessively long
        words = t.split()
        if len(words) > 12:
            t = " ".join(words[:11]) + "…"
        return t or title.strip()

    def _algorithmic_backup_summarize(self, title: str, content: str, article_type: str) -> DigestOutput:
        """
        Extractive NLP heuristics engine that distills the highest-density technical
        sentences from the article into a clean, coherent 2-3 sentence executive brief.
        """
        clean_title = self._clean_title(title)
        
        # Strip HTML, markdown links, images, and redundant whitespace
        text = re.sub(r'<[^>]+>', ' ', content or '')
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
        text = re.sub(r'\s+', ' ', text).strip()

        # Split into individual candidate sentences
        raw_sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if len(s.strip()) >= 25]

        # Domain keywords for technical importance
        ai_keywords = {
            'model', 'models', 'architecture', 'parameters', 'weights', 'training',
            'dataset', 'benchmark', 'benchmarks', 'accuracy', 'performance', 'latency',
            'outperforms', 'state-of-the-art', 'sota', 'reasoning', 'multimodal', 'inference',
            'transformer', 'attention', 'open-source', 'released', 'announces', 'introduces',
            'demonstrates', 'breakthrough', 'scaling', 'reinforcement', 'compute', 'evaluation',
            'agent', 'agents', 'tokens', 'quantization', 'fine-tuning', 'pre-trained'
        }

        boilerplate_patterns = re.compile(
            r'cookie|privacy policy|terms of service|subscribe to|all rights reserved|'
            r'copyright \d{4}|click here|follow us on|sponsored by|read the full article|'
            r'sign up for our newsletter|leave a comment',
            re.IGNORECASE
        )

        candidate_sentences = []
        for idx, s in enumerate(raw_sentences):
            # Skip marketing/legal boilerplate
            if boilerplate_patterns.search(s):
                continue
            
            score = 0.0
            
            # Position weighting (Lead sentences contain primary announcements)
            if idx == 0:
                score += 3.8
            elif idx == 1:
                score += 2.6
            elif idx == 2:
                score += 1.8
            elif idx == len(raw_sentences) - 1:
                score += 1.2

            # Technical domain keyword density
            words = re.findall(r'\b[a-z]{3,}\b', s.lower())
            kw_hits = sum(1 for w in words if w in ai_keywords)
            score += min(kw_hits * 0.9, 4.5)

            # Empirical metrics / quantitative validation (e.g. 85%, 70B, 3x faster)
            if re.search(r'\b\d+(\.\d+)?%|\b\d+([BMK]|x)\b|\b\d+\s*(parameters|tokens|gpus|benchmarks|accuracy)\b', s, re.IGNORECASE):
                score += 2.0

            # Length penalty (favor 55 - 220 characters)
            length = len(s)
            if length < 40:
                score -= 2.0
            elif 70 <= length <= 220:
                score += 1.5
            elif length > 320:
                score -= 1.0

            candidate_sentences.append((s, score, idx))

        # If we have candidate sentences, pick the top 2-3 highest scoring
        if candidate_sentences:
            candidate_sentences.sort(key=lambda x: x[1], reverse=True)
            num_to_pick = min(3 if len(candidate_sentences) >= 3 else 2, len(candidate_sentences))
            top_picked = sorted(candidate_sentences[:num_to_pick], key=lambda x: x[2])
            
            extracted = " ".join(s for s, _, _ in top_picked)
            # Ensure it ends with punctuation
            if not extracted.endswith(('.', '!', '?')):
                extracted += '.'
            
            if len(candidate_sentences) == 1 and len(extracted) < 180:
                summary = f"{extracted} This release marks a significant milestone in AI capabilities, model accessibility, and production systems integration."
            else:
                summary = extracted
        else:
            # Fallback if content was completely empty or too short
            summary = (
                f"{clean_title}. Key developments across frontier AI engineering and research, "
                f"with technical architecture details and empirical benchmarks available in the primary {article_type.upper()} source."
            )

        logger.info(f"✓ [Backup Summarizer] Distilled {len(summary)} char brief for '{clean_title[:40]}...'")
        return DigestOutput(title=clean_title, summary=summary, is_backup=True)
