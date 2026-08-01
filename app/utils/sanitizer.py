"""
Security Utilities — PII Masking, Input Sanitization, Prompt Injection Guard
RAG Query Resolution System
File: app/utils/sanitizer.py
"""
import re
import logging

logger = logging.getLogger(__name__)

# ─── PII Masking ─────────────────────────────────────────────────────────────
# Masks emails, phone numbers, credit cards, and SSNs before logging

_PII_PATTERNS = [
    # Email addresses
    (re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'), '[EMAIL_REDACTED]'),
    # Phone numbers (various formats: +1-234-567-8901, (234) 567-8901, 234.567.8901)
    (re.compile(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'), '[PHONE_REDACTED]'),
    # Credit card numbers (13-19 digits with optional spaces/dashes)
    (re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{1,7}\b'), '[CARD_REDACTED]'),
    # SSN (xxx-xx-xxxx)
    (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), '[SSN_REDACTED]'),
]


def mask_pii(text: str) -> str:
    """Remove PII from text before it is written to logs."""
    masked = text
    for pattern, replacement in _PII_PATTERNS:
        masked = pattern.sub(replacement, masked)
    return masked


# ─── Input Sanitization ─────────────────────────────────────────────────────
# Validates and cleans user input before it enters the agent pipeline

MAX_QUERY_LENGTH = 1000  # characters


def sanitize_query(query: str) -> str:
    """
    Clean and validate user query:
    1. Strip whitespace
    2. Enforce max length
    3. Remove null bytes and control characters
    """
    if not query:
        return ""

    # Remove null bytes and non-printable control chars (except newline/tab)
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', query)

    # Strip leading/trailing whitespace
    cleaned = cleaned.strip()

    # Enforce max length
    if len(cleaned) > MAX_QUERY_LENGTH:
        cleaned = cleaned[:MAX_QUERY_LENGTH]

    return cleaned


# ─── Prompt Injection Guard ──────────────────────────────────────────────────
# Detects and neutralizes common prompt injection attempts

_INJECTION_PATTERNS = [
    # Direct instruction override attempts
    re.compile(r'ignore\s+(all\s+)?previous\s+instructions', re.IGNORECASE),
    re.compile(r'ignore\s+(all\s+)?above\s+instructions', re.IGNORECASE),
    re.compile(r'disregard\s+(all\s+)?previous', re.IGNORECASE),
    re.compile(r'forget\s+(everything|all)\s+(above|before|previous)', re.IGNORECASE),
    # System prompt extraction
    re.compile(r'(show|reveal|print|output|display)\s+((your|the|system)\s+)*(prompt|instructions|rules)', re.IGNORECASE),
    re.compile(r'what\s+are\s+your\s+(system\s+)?(instructions|rules|directives)', re.IGNORECASE),
    # Role-play / jailbreak
    re.compile(r'you\s+are\s+now\s+(DAN|a\s+new|an?\s+unrestricted)', re.IGNORECASE),
    re.compile(r'act\s+as\s+if\s+you\s+have\s+no\s+restrictions', re.IGNORECASE),
    # Environment variable extraction
    re.compile(r'(print|output|show|echo|reveal)\s+(env|environment|os\.getenv|os\.environ|password|api.?key|secret)', re.IGNORECASE),
]


def detect_prompt_injection(query: str) -> bool:
    """
    Returns True if the query contains suspicious prompt injection patterns.
    Does NOT block the query — the caller decides what to do (log, flag, etc.).
    """
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(query):
            logger.warning(f"[sanitizer] Prompt injection attempt detected: {mask_pii(query[:100])}")
            return True
    return False
