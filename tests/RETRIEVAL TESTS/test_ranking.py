"""
Retrieval Tests — Chunk Ranking & Reranking Order
File: tests/RETRIEVAL TESTS/test_ranking.py
"""
import pytest
from unittest.mock import patch, MagicMock
from app.retrieval.pgvector_client import retrieve_similar, rerank_chunks


@patch("app.retrieval.pgvector_client._get_reranker")
def test_rerank_chunks_descending_order(mock_get_reranker):
    """
    Test rerank_chunks directly with a mocked reranker returning fixed scores.
    Assert sorted_chunks are returned in descending rerank_score order.
    """
    mock_reranker = MagicMock()
    # Return fixed scores in arbitrary order for 3 pairs
    mock_reranker.predict.return_value = [0.25, 0.95, 0.60]
    mock_get_reranker.return_value = mock_reranker

    chunks = [
        {"content": "Chunk low score", "metadata": {"id": 1}, "similarity": 0.3},
        {"content": "Chunk high score", "metadata": {"id": 2}, "similarity": 0.8},
        {"content": "Chunk mid score", "metadata": {"id": 3}, "similarity": 0.5},
    ]

    reranked = rerank_chunks(query="test query", chunks=chunks, top_n=3)

    assert len(reranked) == 3
    scores = [c["rerank_score"] for c in reranked]
    assert scores == [0.95, 0.60, 0.25]
    assert scores == sorted(scores, reverse=True)
    assert reranked[0]["content"] == "Chunk high score"
    assert reranked[1]["content"] == "Chunk mid score"
    assert reranked[2]["content"] == "Chunk low score"


@patch("app.retrieval.pgvector_client._get_reranker")
@patch("app.retrieval.pgvector_client.get_connection")
@patch("app.retrieval.pgvector_client.get_bedrock_embedding")
def test_retrieve_similar_ranking_order(mock_get_embedding, mock_get_conn, mock_get_reranker):
    """
    Test retrieve_similar with mocked embedding, db connection, and reranker.
    Given fake cursor.fetchall() results with known similarity scores,
    assert the returned list order matches descending similarity/rerank order.
    """
    mock_get_embedding.return_value = [0.1] * 1024

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_get_conn.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cur

    mock_reranker = MagicMock()
    mock_reranker.predict.return_value = [0.40, 0.90, 0.70]
    mock_get_reranker.return_value = mock_reranker

    # Fake database rows: (content, metadata, similarity)
    fake_rows = [
        ("Doc C", {"source": "doc3.pdf"}, 0.40),
        ("Doc A", {"source": "doc1.pdf"}, 0.90),
        ("Doc B", {"source": "doc2.pdf"}, 0.70),
    ]
    mock_cur.fetchall.return_value = fake_rows

    results = retrieve_similar("What is the return policy?", top_k=3, min_similarity=0.3)

    assert len(results) == 3
    retrieved_scores = [r["rerank_score"] for r in results]
    assert retrieved_scores == [0.90, 0.70, 0.40]
    assert results[0]["content"] == "Doc A"
    assert results[1]["content"] == "Doc B"
    assert results[2]["content"] == "Doc C"
