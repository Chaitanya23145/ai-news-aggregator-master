import re
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# List of well-known disposable/burner email providers
DISPOSABLE_DOMAINS = {
    "mailinator.com", "tempmail.com", "temp-mail.org", "guerrillamail.com",
    "guerrillamailblock.com", "yopmail.com", "yopmail.fr", "trashmail.com",
    "dispostable.com", "sharklasers.com", "10minutemail.com", "10minutemail.net",
    "throwawaymail.com", "burnermail.io", "getairmail.com", "fakeinbox.com",
    "fakemailgenerator.com", "crazymailing.com", "generator.email", "nada.ltd",
    "maildrop.cc", "tempail.com", "dropmail.me", "mohmal.com", "inboxkitten.com",
    "tempinbox.com", "guerrillamail.net", "guerrillamail.org", "grr.la"
}

# Common domain typos
TYPO_DOMAINS = {
    "gmai.com": "gmail.com",
    "gamil.com": "gmail.com",
    "gmial.com": "gmail.com",
    "gnail.com": "gmail.com",
    "gmaill.com": "gmail.com",
    "hotmial.com": "hotmail.com",
    "hotmaill.com": "hotmail.com",
    "outlok.com": "outlook.com",
    "outloo.com": "outlook.com",
    "yaho.com": "yahoo.com",
    "yahooo.com": "yahoo.com",
    "protonmial.com": "proton.me",
    "protonmail.co": "proton.me"
}

# Known fake/gibberish addresses
FAKE_ADDRESSES = {
    "test@test.com", "asdf@asdf.com", "fake@fake.com", "admin@admin.com",
    "abc@xyz.com", "user@example.com", "a@a.com", "me@me.com",
    "someone@example.com", "none@none.com", "no@no.com"
}


def validate_email_address(email: str) -> Tuple[bool, str]:
    """
    Performs comprehensive multi-layer email verification:
    1. Syntax and RFC 5322 format.
    2. Disposable and temporary email filtering.
    3. Typo detection with smart recommendations.
    4. Gibberish and placeholder rejection.
    5. Real-time DNS MX record verification to ensure domain actually exists and can receive mail.
    """
    clean_email = (email or "").strip().lower()
    
    if not clean_email:
        return False, "Email address cannot be empty."

    if len(clean_email) > 254:
        return False, "Email address exceeds maximum length (254 characters)."

    # RFC 5322 compliant regex check
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, clean_email):
        return False, "Invalid email format. Please enter a valid address (e.g. name@domain.com)."

    local_part, domain = clean_email.split('@', 1)

    if len(local_part) > 64:
        return False, "Email username portion cannot exceed 64 characters."

    if ".." in local_part or ".." in domain:
        return False, "Email cannot contain consecutive periods."

    if local_part.startswith(".") or local_part.endswith("."):
        return False, "Email cannot start or end with a period."

    # Block known fake placeholder addresses
    if clean_email in FAKE_ADDRESSES:
        return False, "Please enter a genuine personal or work email address."

    # Block common disposable temporary email domains
    if domain in DISPOSABLE_DOMAINS:
        return False, "Temporary and disposable email addresses are not supported. Please use a valid personal or corporate email."

    # Detect common typos and help the user
    if domain in TYPO_DOMAINS:
        suggested = TYPO_DOMAINS[domain]
        return False, f"Domain typo detected: '{domain}'. Did you mean '@{suggested}'?"

    # Check for domain validity via DNS MX records
    try:
        import dns.resolver
        # Resolve MX records with a tight timeout to prevent slow latency
        answers = dns.resolver.resolve(domain, 'MX', lifetime=2.5)
        if not answers or len(answers) == 0:
            return False, f"The domain '@{domain}' has no active mail server (MX records) to receive emails."
    except Exception as dns_err:
        err_str = str(dns_err)
        # Check if NXDOMAIN (domain does not exist)
        if "NXDOMAIN" in err_str or "does not exist" in err_str:
            return False, f"The domain '@{domain}' does not exist. Please check your spelling."
        
        # If MX lookup timed out or failed, try resolving A record as fallback
        try:
            import dns.resolver
            a_records = dns.resolver.resolve(domain, 'A', lifetime=2.5)
            if not a_records or len(a_records) == 0:
                return False, f"The domain '@{domain}' cannot receive mail."
        except Exception:
            # If both MX and A lookups fail, the domain cannot receive mail
            return False, f"The domain '@{domain}' does not exist or has no active mail server."

    return True, "Valid"

