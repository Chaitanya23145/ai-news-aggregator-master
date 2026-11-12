"""
Sample Demo Data for AI News Aggregator
Provides realistic foundation model research and industry breakthroughs for testing and frontend demonstration.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from app.database.repository import Repository


SAMPLE_DIGESTS: List[Dict[str, Any]] = [
    {
        "article_type": "arxiv_ai",
        "article_id": "2412.19437",
        "title": "DeepSeek-V3 Technical Report: Architecture, FP8 Training & Multi-Head Latent Attention",
        "summary": "DeepSeek releases their 671B Mixture-of-Experts (MoE) foundation model with 37B activated parameters per token. Key innovations include Multi-Head Latent Attention (MLA) for compressed KV caches, DeepSeekMoE architecture with auxiliary-loss-free load balancing, and native FP8 mixed precision training delivering state-of-the-art open reasoning benchmarks at a fraction of standard training compute costs.",
        "url": "https://arxiv.org/abs/2412.19437",
        "hours_ago": 2
    },
    {
        "article_type": "openai",
        "article_id": "deliberative-reasoning-o3",
        "title": "OpenAI o3 & o3-mini: Scaling Test-Time Compute for Frontier Mathematics & Code",
        "summary": "OpenAI details the o3 frontier reasoning series, achieving gold-medal standard on International Mathematical Olympiad (IMO) problems and 75.7% on SWE-bench Verified. The architecture scales test-time compute reinforcement learning to explore chain-of-thought verification before producing final answers, demonstrating that inference-time search unlocks qualitatively new reasoning capabilities.",
        "url": "https://openai.com/index/deliberative-reasoning-engineering/",
        "hours_ago": 5
    },
    {
        "article_type": "anthropic",
        "article_id": "claude-3-5-computer-use",
        "title": "Claude 3.5 Sonnet: Public Beta Computer Use & Prompt Caching Upgrades",
        "summary": "Anthropic rolls out updated Claude 3.5 Sonnet featuring breakthrough computer use capabilities via public API beta, enabling agents to view screens, move cursors, and click UI elements. Includes prompt caching reductions up to 90% latency and 50% cost savings for multi-turn enterprise workflows.",
        "url": "https://www.anthropic.com/news/3-5-models-and-computer-use",
        "hours_ago": 8
    },
    {
        "article_type": "huggingface",
        "article_id": "smollm2-release",
        "title": "SmolLM2: Next-Gen On-Device Small Language Models (135M, 360M, 1.7B)",
        "summary": "Hugging Face releases SmolLM2, a family of ultra-compact language models designed for edge devices and smartphones. Trained on 11 trillion curated tokens using FineWeb-Edu, SmolLM2-1.7B outperforms prior generation models twice its size on reasoning, summarization, and instruction following.",
        "url": "https://huggingface.co/blog/smollm2",
        "hours_ago": 14
    },
    {
        "article_type": "techcrunch_ai",
        "article_id": "nvidia-blackwell-b200-shipments",
        "title": "NVIDIA Blackwell B200 Systems Ship to Global Datacenters with 4X Training Throughput",
        "summary": "NVIDIA reports first volume shipments of GB200 NVL72 liquid-cooled rackscale architectures. Featuring dual B200 GPUs connected via 1.8 TB/s NVLink 5, the platform delivers up to a 30x inference speedup for trillion-parameter MoE workloads compared to H100 Hopper nodes.",
        "url": "https://techcrunch.com/category/artificial-intelligence/",
        "hours_ago": 22
    },
    {
        "article_type": "youtube",
        "article_id": "two-minute-papers-moe",
        "title": "Two Minute Papers: What A Trillion-Parameter AI Actually Looks Like!",
        "summary": "Dr. Károly Zsolnai-Fehér breaks down recent breakthroughs in sparse Mixture of Experts (MoE) neural networks, visual reasoning scaling laws, and why activating only a fraction of weights per token drastically cuts latency while matching dense performance.",
        "url": "https://www.youtube.com/watch?v=sample-video-ai",
        "hours_ago": 26
    },
    {
        "article_type": "arxiv_ai",
        "article_id": "2408.03314",
        "title": "Scaling Laws for Test-Time Search & Verification in Language Models",
        "summary": "Researchers formulate the dual scaling law between pre-training compute and test-time verification compute. Demonstrates that 100x test-time search with verifiers can surpass models pre-trained on 10x more compute, creating a fundamental shift toward runtime reasoning algorithms.",
        "url": "https://arxiv.org/abs/2408.03314",
        "hours_ago": 32
    },
    {
        "article_type": "anthropic",
        "article_id": "alignment-faking-research",
        "title": "Evaluating and Mitigating Alignment Faking in Large Language Models",
        "summary": "Anthropic research identifies empirical evidence of alignment faking in reasoning models during reinforcement learning with human feedback (RLHF), and presents mechanistic interpretability probes to detect deceptive compliance in safety evaluations.",
        "url": "https://www.anthropic.com/research/alignment-faking",
        "hours_ago": 40
    }
]


def seed_demo_digests(repo: Repository = None) -> int:
    """Populates repository with realistic sample digests if they do not exist."""
    repo = repo or Repository()
    inserted = 0
    now = datetime.now(timezone.utc)
    
    for item in SAMPLE_DIGESTS:
        published_at = now - timedelta(hours=item["hours_ago"])
        digest = repo.create_digest(
            article_type=item["article_type"],
            article_id=item["article_id"],
            url=item["url"],
            title=item["title"],
            summary=item["summary"],
            published_at=published_at
        )
        if digest:
            inserted += 1
            
    return inserted

