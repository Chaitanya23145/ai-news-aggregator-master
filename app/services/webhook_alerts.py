"""
==========================================================
AI News Aggregator - Webhook Alert Notification Service
Sends real-time Slack & Discord alerts for breaking AI papers
Author : Chaitanya Upadhyay
==========================================================
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
ALERT_MIN_SCORE = float(os.getenv("ALERT_MIN_SCORE", "8.0"))


class WebhookAlertService:
    def __init__(
        self,
        slack_url: Optional[str] = None,
        discord_url: Optional[str] = None,
        min_score: float = ALERT_MIN_SCORE
    ):
        self.slack_url = slack_url or SLACK_WEBHOOK_URL
        self.discord_url = discord_url or DISCORD_WEBHOOK_URL
        self.min_score = min_score

    def should_alert(self, relevance_score: float) -> bool:
        """Determines if paper/article meets relevance threshold for immediate push alert."""
        return relevance_score >= self.min_score

    def send_slack_alert(
        self,
        title: str,
        summary: str,
        url: str,
        source: str = "arXiv AI",
        relevance_score: float = 9.0
    ) -> bool:
        """Dispatches rich Slack Block Kit notification message."""
        if not self.slack_url:
            logger.debug("Slack webhook URL not configured, skipping Slack alert.")
            return False

        payload = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🚨 Breaking AI Development ({source})",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*<{url}|{title}>*\n\n{summary}"
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"⭐ *Relevance Score:* `{relevance_score:.1f}/10` | 🕒 *Time:* {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
                        }
                    ]
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "📖 Read Full Source",
                                "emoji": True
                            },
                            "url": url,
                            "style": "primary"
                        }
                    ]
                }
            ]
        }

        try:
            resp = requests.post(self.slack_url, json=payload, timeout=5)
            if resp.status_code == 200:
                logger.info(f"Slack alert sent successfully for: {title}")
                return True
            else:
                logger.warning(f"Slack webhook returned status {resp.status_code}: {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Failed to deliver Slack webhook alert: {e}")
            return False

    def send_discord_alert(
        self,
        title: str,
        summary: str,
        url: str,
        source: str = "arXiv AI",
        relevance_score: float = 9.0
    ) -> bool:
        """Dispatches Discord Rich Embed notification."""
        if not self.discord_url:
            logger.debug("Discord webhook URL not configured, skipping Discord alert.")
            return False

        # Color gradient: Emerald (0x10B981) for high relevance, Purple (0x8B5CF6) for research
        embed_color = 0x8B5CF6 if "arxiv" in source.lower() else 0x10B981

        payload = {
            "username": "AI Intelligence Bot",
            "avatar_url": "https://img.icons8.com/color/96/artificial-intelligence.png",
            "embeds": [
                {
                    "title": f"🚨 {title}",
                    "url": url,
                    "description": summary,
                    "color": embed_color,
                    "fields": [
                        {
                            "name": "📡 Source",
                            "value": f"`{source}`",
                            "inline": True
                        },
                        {
                            "name": "⭐ Relevance Score",
                            "value": f"`{relevance_score:.1f} / 10`",
                            "inline": True
                        },
                        {
                            "name": "⚡ Engine",
                            "value": "Groq Llama-3.3-70B",
                            "inline": True
                        }
                    ],
                    "footer": {
                        "text": "AI News Aggregator • Autonomous Breaking Alert"
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }
            ]
        }

        try:
            resp = requests.post(self.discord_url, json=payload, timeout=5)
            if resp.status_code in (200, 204):
                logger.info(f"Discord alert sent successfully for: {title}")
                return True
            else:
                logger.warning(f"Discord webhook returned status {resp.status_code}: {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Failed to deliver Discord webhook alert: {e}")
            return False

    def dispatch_alert(
        self,
        title: str,
        summary: str,
        url: str,
        source: str = "arXiv AI",
        relevance_score: float = 9.0
    ) -> Dict[str, Any]:
        """Dispatches alerts across all configured webhooks."""
        results = {
            "title": title,
            "relevance_score": relevance_score,
            "slack_sent": False,
            "discord_sent": False,
        }

        if not self.should_alert(relevance_score):
            logger.info(f"Score {relevance_score} below threshold {self.min_score}; skipping webhook alerts.")
            return results

        results["slack_sent"] = self.send_slack_alert(title, summary, url, source, relevance_score)
        results["discord_sent"] = self.send_discord_alert(title, summary, url, source, relevance_score)
        return results


_webhook_service = WebhookAlertService()

def get_webhook_service() -> WebhookAlertService:
    return _webhook_service
