import os
import sys
from langchain_core.documents import Document

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from app.retrieval.pgvector_client import store_chunks, get_connection

def test_deduplication():
    test_chunk = Document(
        page_content="Unique test chunk content for deduplication verification test.",
        metadata={"source": "test_dedup_source"}
    )
    
    # Store initial chunk
    store_chunks([test_chunk])
    
    # Attempt storing duplicate chunk
    store_chunks([test_chunk])
    
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
