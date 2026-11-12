"""
==========================================================
Synapse AI - Automated Content Safety & Review Moderation
Detects vulgarity, hate speech, and abusive terms in English & Hinglish
==========================================================
"""

import re
from typing import Tuple, Optional

# Curated list of abusive, profane, and vulgar terms (English + Hinglish)
PROFANITY_LIST = {
    # English Profanities & Slurs
    "fuck", "fucker", "fucking", "fucked", "motherfucker", "shit", "bullshit",
    "bitch", "bitches", "asshole", "bastard", "cunt", "dick", "pussy",
    "slut", "whore", "retard", "fag", "faggot", "nigger", "nigga",
    "idiot", "dumbass", "moron", "scam", "fraudsters",
    
    # Hindi / Hinglish Profanities
    "chutiya", "chutiye", "chutya", "madarchod", "madarshod", "mc", 
    "bhenchod", "behenchod", "bc", "bhosdike", "bhosdi", "bhosadike",
    "harami", "gaand", "gand", "gandu", "lodu", "laude", "lavde",
    "randi", "kamina", "kamine", "saala", "saale", "kutta", "kutti"
}


def normalize_text(text: str) -> str:
    """Lowercases text, removes leetspeak and collapses repeating letters."""
    if not text:
        return ""
    text = text.lower()
    # Replace common leetspeak substitutions
    subs = {
        '@': 'a', '$': 's', '0': 'o', '1': 'i', '!': 'i', '3': 'e',
        '5': 's', '7': 't', '+': 't', '*': ' '
    }
    for char, rep in subs.items():
        text = text.replace(char, rep)
    
    # Strip non-alphanumeric except whitespace
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def contains_abusive_language(text: str) -> Tuple[bool, Optional[str]]:
    """
    Evaluates text for abusive, vulgar, or inappropriate terms.
    Returns: (is_toxic: bool, flagged_word: Optional[str])
    """
    if not text:
        return False, None
    
    normalized = normalize_text(text)
    words = set(normalized.split())
    
    # 1. Exact word match
    intersection = words.intersection(PROFANITY_LIST)
    if intersection:
        return True, list(intersection)[0]
    
    # 2. Substring match for longer composite bad words (length >= 4)
    for bad_word in PROFANITY_LIST:
        if len(bad_word) >= 4:
            pattern = rf"\b{bad_word}\b"
            if re.search(pattern, normalized):
                return True, bad_word
            # Check combined words like "fuckyou" or "chutiyagiri"
            if bad_word in normalized and len(bad_word) >= 5:
                return True, bad_word
                
    return False, None

