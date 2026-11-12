"""
==========================================================
AI News Aggregator - User Preference Fine-Tuning Manager
Author : Chaitanya Upadhyay
==========================================================
"""

import os
import json
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

PREFS_FILE = os.path.join(os.path.dirname(__file__), "user_preferences.json")

DEFAULT_PREFERENCES: Dict[str, Any] = {
    "preferred_topics": [
        "LLM Reasoning & Architecture",
        "Autonomous AI Agents",
        "Open Source Foundation Models",
        "Vision & Multimodal Intelligence",
        "AI Hardware & Inference Acceleration",
        "Robotics & Embodied AI"
    ],
    "excluded_topics": [
        "Cryptocurrency & Web3",
        "Celebrity AI Gossip",
        "Generic Marketing Press Releases"
    ],
    "technical_depth_weight": 4.0,  # 1.0 (High-level overview) to 5.0 (Deep technical research)
    "min_relevance_score": 7.5,
    "slack_webhook_url": "",
    "discord_webhook_url": "",
    "enable_slack_alerts": False,
    "enable_discord_alerts": False,
}


class PreferenceManager:
    def __init__(self, filepath: str = PREFS_FILE):
        self.filepath = filepath
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not os.path.exists(self.filepath):
            self.save_preferences(DEFAULT_PREFERENCES)

    def get_preferences(self) -> Dict[str, Any]:
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Merge defaults for any missing keys
                for k, v in DEFAULT_PREFERENCES.items():
                    if k not in data:
                        data[k] = v
                return data
        except Exception as e:
            logger.warning(f"Failed to read preferences from {self.filepath}: {e}, returning defaults.")
            return DEFAULT_PREFERENCES.copy()

    def save_preferences(self, prefs: Dict[str, Any]) -> bool:
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(prefs, f, indent=2)
            logger.info("User preferences updated successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to save preferences to {self.filepath}: {e}")
            return False

    def update_preferences(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        current = self.get_preferences()
        current.update(updates)
        self.save_preferences(current)
        return current

    def reset_to_defaults(self) -> Dict[str, Any]:
        self.save_preferences(DEFAULT_PREFERENCES)
        return DEFAULT_PREFERENCES.copy()


_pref_manager = PreferenceManager()

def get_preference_manager() -> PreferenceManager:
    return _pref_manager
