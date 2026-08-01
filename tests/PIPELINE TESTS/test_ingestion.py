"""
Pipeline Tests — Ingestion Pipeline
File: tests/PIPELINE TESTS/test_ingestion.py
"""
import pytest
from unittest.mock import patch, MagicMock
from langchain_core.documents import Document
from app.ingestion.pipeline import ingest


@patch("app.ingestion.pipeline.store_chunks")
@patch("app.ingestion.pipeline.PyPDFLoader")
@patch("app.ingestion.pipeline.boto3.client")
def test_ingest_pipeline_flow(mock_boto_client, mock_loader_cls, mock_store_chunks):
    """
    Test: ingest() calls load_document_from_s3, chunk_documents, then store_chunks
    with the chunked output — mock PyPDFLoader.load to return fake documents,
    assert store_chunks was called once.
    """
    fake_doc = Document(
        page_content="This is a test PDF document for ingestion.",
        metadata={"source": "test.pdf", "page": 1},
    )
    mock_loader_instance = MagicMock()
    mock_loader_instance.load.return_value = [fake_doc]
    mock_loader_cls.return_value = mock_loader_instance

    mock_s3_instance = MagicMock()
    mock_boto_client.return_value = mock_s3_instance

    s3_key = "raw-documents/test.pdf"
    ingest(s3_key)

    mock_s3_instance.download_file.assert_called_once()
    mock_loader_instance.load.assert_called_once()
    mock_store_chunks.assert_called_once()

    # Check that store_chunks was called with non-empty chunk list
    passed_chunks = mock_store_chunks.call_args[0][0]
    assert len(passed_chunks) > 0
    assert "test PDF document" in passed_chunks[0].page_content
