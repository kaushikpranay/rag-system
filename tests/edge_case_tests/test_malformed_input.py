"""
Edge Case Tests — Query Sanitization & Malformed Input
File: tests/EDGE CASE TESTS/test_malformed_input.py
"""
import pytest
from app.utils.sanitizer import sanitize_query, MAX_QUERY_LENGTH


def test_null_bytes_and_control_chars_stripped():
    raw_input = "Hello\x00 World!\x07\x1f"
    assert sanitize_query(raw_input) == "Hello World!"


def test_queries_over_max_length_truncated():
    long_query = "a" * (MAX_QUERY_LENGTH + 500)
    sanitized = sanitize_query(long_query)
    assert len(sanitized) == MAX_QUERY_LENGTH
    assert sanitized == "a" * MAX_QUERY_LENGTH


@pytest.mark.parametrize(
    "empty_input",
    [
        "",
        "   ",
        "\t\n\r",
        None,
    ],
)
def test_empty_or_whitespace_returns_empty_string(empty_input):
    assert sanitize_query(empty_input) == ""


def test_normal_input_whitespace_stripped():
    input_text = "  what is the return policy?   "
    assert sanitize_query(input_text) == "what is the return policy?"
