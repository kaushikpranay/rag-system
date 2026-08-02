"""
Pipeline Tests — Embedding Schema & Chunk Skipping
File: tests/PIPELINE TESTS/test_embedding_schema.py
"""
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.documents import Document
from app.retrieval.pgvector_client import store_chunks


@patch("app.retrieval.pgvector_client.get_connection")
@patch("app.retrieval.pgvector_client.get_bedrock_embedding")
def test_empty_chunk_content_is_skipped(mock_get_embedding, mock_get_conn):
    """
    Test: a chunk with empty content after stripping is skipped (not passed to embedding call).
    """
    mock_get_embedding.return_value = [0.1] * 1024

    empty_chunk = Document(page_content="   \x00  \t\n  ", metadata={"source": "empty.pdf"})
    result = store_chunks([empty_chunk])

    assert result == 0
    mock_get_embedding.assert_not_called()
    mock_get_conn.assert_not_called()


@patch("app.retrieval.pgvector_client.get_connection")
@patch("app.retrieval.pgvector_client.get_bedrock_embedding")
def test_empty_embedding_returns_skipped(mock_get_embedding, mock_get_conn):
    """
    Test: a chunk where get_bedrock_embedding returns [] (empty) is skipped, not inserted.
    """
    mock_get_embedding.return_value = []

    valid_chunk = Document(page_content="Valid document content for testing.", metadata={"source": "valid.pdf"})
    result = store_chunks([valid_chunk])

    assert result == 0
    mock_get_embedding.assert_called_once_with("Valid document content for testing.")
    mock_get_conn.assert_not_called()


@patch("app.retrieval.pgvector_client.execute_values")
@patch("app.retrieval.pgvector_client.get_connection")
@patch("app.retrieval.pgvector_client.get_bedrock_embedding")
def test_valid_chunk_inserted(mock_get_embedding, mock_get_conn, mock_execute_values):
    """
    Test: a valid chunk with 1024-len embedding is properly formatted and inserted via execute_values.
    """
    mock_get_embedding.return_value = [0.1] * 1024
    mock_execute_values.return_value = [(1,)]

    mock_conn = MagicMock()
    mock_get_conn.return_value = mock_conn

    valid_chunk = Document(page_content="Valid chunk text.", metadata={"source": "doc.pdf"})
    result = store_chunks([valid_chunk])

    assert result == 1
    mock_get_embedding.assert_called_once_with("Valid chunk text.")
    mock_get_conn.assert_called_once()
    mock_execute_values.assert_called_once()
