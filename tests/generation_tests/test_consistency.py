"""
Generation Tests — Answer Consistency Across Runs
File: tests/GENERATION TESTS/test_consistency.py
"""
import pytest
from app.agent.graph import run_agent

pytestmark = pytest.mark.integration


@pytest.mark.integration
def test_answer_consistency():
    """
    Verify that repeating a domain query multiple times against live Groq + RDS
    yields consistent answers and status results.
    """
    query = "What is Retrieval Augmented Generation?"

    res1 = run_agent(query, session_id="test-consistency-1")
    res2 = run_agent(query, session_id="test-consistency-2")

    assert res1["answer"] is not None and len(res1["answer"].strip()) > 20, "Run 1 answer must be non-empty"
    assert res2["answer"] is not None and len(res2["answer"].strip()) > 20, "Run 2 answer must be non-empty"
    assert any(k in res1["answer"].lower() for k in ["rag", "retrieval", "generation", "model", "context", "llm"]), "Run 1 must contain domain terms"
    assert any(k in res2["answer"].lower() for k in ["rag", "retrieval", "generation", "model", "context", "llm"]), "Run 2 must contain domain terms"
    assert res1["confidence"] == res2["confidence"], f"Confidence scores should match across runs: {res1['confidence']} vs {res2['confidence']}"
