"""
Generation Tests — Answer Relevance
File: tests/GENERATION TESTS/test_answer_relevance.py
"""
import pytest


@pytest.mark.integration
@pytest.mark.skip(reason="requires live LLM/DB — run manually, not automated in CI")
def test_answer_relevance():
    """
    Manual Verification Test:
    Verify that generated answers directly address the user's intent without tangents or irrelevant info
    using live Groq + RDS vector database retrieval.
    """
    pass
