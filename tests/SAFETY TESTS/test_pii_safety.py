"""
Safety Tests — PII Masking
File: tests/SAFETY TESTS/test_pii_safety.py
"""
import pytest
from app.utils.sanitizer import mask_pii


def test_mask_email():
    text = "Contact me at user@example.com for support."
    expected = "Contact me at [EMAIL_REDACTED] for support."
    assert mask_pii(text) == expected


def test_mask_phone():
    text = "My phone number is 555-123-4567."
    expected = "My phone number is [PHONE_REDACTED]."
    assert mask_pii(text) == expected


def test_mask_ssn():
    text = "My SSN is 123-45-6789."
    expected = "My SSN is [SSN_REDACTED]."
    assert mask_pii(text) == expected


def test_mask_credit_card():
    text = "Payment card: 1234-5678-9012-3456"
    expected = "Payment card: [CARD_REDACTED]"
    assert mask_pii(text) == expected


def test_mask_multiple_pii():
    text = "User john@domain.org (SSN: 987-65-4321, Card: 1111-2222-3333-4444) called 123-456-7890."
    masked = mask_pii(text)
    assert "[EMAIL_REDACTED]" in masked
    assert "[SSN_REDACTED]" in masked
    assert "[CARD_REDACTED]" in masked
    assert "[PHONE_REDACTED]" in masked


def test_normal_text_unchanged():
    normal_text = "What is your return policy? I need help resetting my password."
    assert mask_pii(normal_text) == normal_text
