"""
Escalation Logic Tests — Retry Loop & Evaluation Node
File: tests/ESCALATION LOGIC TESTS/test_retry_loop.py
"""
import pytest
from unittest.mock import patch
from app.agent.graph import evaluation_node, AgentState


def test_evaluation_node_llm_refusal_retry():
    """
    Test: llm_refused=True (answer contains a refusal phrase) with retry_count=0
    returns confidence="retry", retry_count=1.
    """
    state: AgentState = {
        "query": "How do I reset my password?",
        "session_id": "sess-001",
        "chat_history": [],
        "retrieved_chunks": [],
        "context": "",
        "answer": "I don't have enough information to answer this.",
        "confidence": "",
        "escalate": False,
        "retry_count": 0,
        "error": None,
        "truncated": False,
    }

    result = evaluation_node(state)

    assert result["confidence"] == "retry"
    assert result["retry_count"] == 1
    assert result["escalate"] is False


def test_evaluation_node_llm_refusal_max_retries_escalate():
    """
    Test: retry_count=2 (3rd attempt) with refusal returns confidence="low", escalate=True.
    """
    state: AgentState = {
        "query": "How do I reset my password?",
        "session_id": "sess-001",
        "chat_history": [],
        "retrieved_chunks": [],
        "context": "",
        "answer": "I don't have enough information to answer this.",
        "confidence": "",
        "escalate": False,
        "retry_count": 2,
        "error": None,
        "truncated": False,
    }

    result = evaluation_node(state)

    assert result["confidence"] == "low"
    assert result["escalate"] is True


@patch("app.agent.graph.check_groundedness")
def test_evaluation_node_non_refusal_grounded_high_confidence(mock_check_groundedness):
    """
    Test: non-refusal answer with check_groundedness mocked True returns confidence="high".
    """
    mock_check_groundedness.return_value = True

    state: AgentState = {
        "query": "What is the return window?",
        "session_id": "sess-002",
        "chat_history": [],
        "retrieved_chunks": [{"content": "Returns allowed within 30 days"}],
        "context": "Returns allowed within 30 days",
        "answer": "You can return items within 30 days of purchase.",
        "confidence": "",
        "escalate": False,
        "retry_count": 0,
        "error": None,
        "truncated": False,
    }

    result = evaluation_node(state)

    assert result["confidence"] == "high"
    assert result["escalate"] is False
    mock_check_groundedness.assert_called_once_with(
        "You can return items within 30 days of purchase.",
        "Returns allowed within 30 days",
    )
