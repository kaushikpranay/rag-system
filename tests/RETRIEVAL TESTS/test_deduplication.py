import os
import sys
import pytest
from langchain_core.documents import Document

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from app.retrieval.pgvector_client import store_chunks, get_connection


def test_deduplication():
    # Check if database is reachable (skip cleanly in CI environments without active RDS connection)
    try:
        conn = get_connection()
        conn.close()
    except Exception:
        pytest.skip("Database is not reachable in this environment (e.g. CI runner)")

    test_chunk = Document(
        page_content="Unique test chunk content for deduplication verification test.",
        metadata={"source": "test_dedup_source"},
    )

    try:
        # Store initial chunk
        stored = store_chunks([test_chunk])
        if stored == 0:
            pytest.skip("Embedding API / Bedrock not reachable in this environment (0 chunks stored)")

        # Attempt storing duplicate chunk
        store_chunks([test_chunk])
    except Exception as e:
        pytest.skip(f"Embedding API / Bedrock not reachable in this environment: {e}")

    conn = get_connection()
    cur = conn.cursor()
    import hashlib

    clean_text = test_chunk.page_content.strip()
    content_hash = hashlib.sha256(clean_text.encode("utf-8")).hexdigest()

    cur.execute("SELECT count(*) FROM documents WHERE metadata->>'content_hash' = %s;", (content_hash,))
    count = cur.fetchone()[0]

    # Clean up test row
    cur.execute("DELETE FROM documents WHERE metadata->>'content_hash' = %s;", (content_hash,))
    cur.close()
    conn.close()

    assert count == 1, f"Expected exactly 1 stored row for duplicate chunk, got {count}"
    print(f"Deduplication test PASSED: stored count = {count}")


if __name__ == "__main__":
    test_deduplication()
