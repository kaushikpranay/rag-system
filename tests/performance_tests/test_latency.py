"""
Performance Tests — End-to-End Latency
File: tests/PERFORMANCE TESTS/test_latency.py
"""
import time
import pytest
from app.retrieval.pgvector_client import retrieve_similar
from app.agent.graph import run_agent

pytestmark = pytest.mark.integration


@pytest.mark.integration
def test_end_to_end_latency():
    """
    Measure latency for live vector database retrieval and live agent execution.
    """
    query = "What is semantic vector search?"

    # Retrieval latency check against live documents table
    t0 = time.time()
    chunks = retrieve_similar(query, top_k=3, min_similarity=0.2)
    t_retrieval = time.time() - t0

    assert len(chunks) > 0, "Retrieval must return matching chunks from live documents table"
    assert t_retrieval < 10.0, f"Retrieval latency should be under 10.0 seconds, got {t_retrieval:.2f}s"
    assert chunks[0]["similarity"] >= 0.2, f"Top chunk similarity should meet minimum threshold: {chunks[0]['similarity']:.2f}"

    # Agent latency check
    t1 = time.time()
    res = run_agent(query)
    t_agent = time.time() - t1

    assert res["answer"] is not None and len(res["answer"].strip()) > 10, "Agent answer must not be empty"
    assert t_agent < 30.0, f"Agent execution latency should be under 30.0 seconds, got {t_agent:.2f}s"
