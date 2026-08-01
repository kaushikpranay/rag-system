"""
Retrieval Tests — Negative Retrieval & Unrelated Queries
File: tests/RETRIEVAL TESTS/test_negative_retrieval.py
"""
import pytest


@pytest.mark.integration
@pytest.mark.skip(reason="requires live LLM/DB — run manually, not automated in CI")
def test_negative_retrieval_unrelated_queries():
    """
    Manual Verification Test:
    Verify that completely unrelated queries return vector similarity scores below min_similarity
    and retrieve 0 chunks against live pgvector database.
    """
    pass
