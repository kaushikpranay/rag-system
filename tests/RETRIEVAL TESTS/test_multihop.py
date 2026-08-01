"""
Retrieval Tests — Multi-Hop Question Answering
File: tests/RETRIEVAL TESTS/test_multihop.py
"""
import pytest
from app.retrieval.pgvector_client import retrieve_similar
from app.agent.graph import run_agent

pytestmark = pytest.mark.integration


@pytest.mark.integration
def test_multihop_reasoning():
    """
    Verify multi-hop retrieval and reasoning across live document chunks.
    """
    query = "What is RAG and how are document chunks retrieved?"

    # Retrieval check against live documents table
    chunks = retrieve_similar(query, top_k=5, min_similarity=0.2)
    assert len(chunks) > 0, "Multi-hop query should retrieve candidate chunks from live documents table"
    assert "rerank_score" in chunks[0] or "similarity" in chunks[0], "Retrieved chunks must include ranking score metrics"

    # Agent graph execution check
    res = run_agent(query)
    assert res["answer"] is not None and len(res["answer"].strip()) > 30, "Agent answer for multi-hop query must be non-empty"
    assert any(term in res["answer"].lower() for term in ["vector", "embedding", "retriev", "rag", "chunk", "document"]), "Answer should cover multi-hop conceptual components"
