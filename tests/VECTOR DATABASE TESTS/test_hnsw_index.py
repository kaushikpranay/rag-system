import pytest
from conftest import skip_if_no_db, generate_random_vector

def test_hnsw_index_existence_and_integrity(db_conn):
    """
    Requirement 3: Verify HNSW index existence, valid access method, and integrity.
    """
    skip_if_no_db()
    cur = db_conn.cursor()
    
    # 1. Check if 'hnsw' access method exists in pg_am
    cur.execute("SELECT amname FROM pg_am WHERE amname = 'hnsw';")
    am = cur.fetchone()
    assert am is not None, "pgvector 'hnsw' access method not found in pg_am"
    assert am[0] == "hnsw"
    
    # 2. Check if HNSW index exists on documents table
    cur.execute("""
        SELECT indexname, indexdef 
        FROM pg_indexes 
        WHERE tablename = 'documents' AND indexname = 'idx_documents_embedding_hnsw';
    """)
    idx = cur.fetchone()
    assert idx is not None, "HNSW index 'idx_documents_embedding_hnsw' does not exist on documents table"
    assert "using hnsw" in idx[1].lower(), f"Index definition does not use HNSW: {idx[1]}"
    assert "m=" in idx[1].lower() and "16" in idx[1], f"Index definition missing tuned parameter m=16: {idx[1]}"
    assert "ef_construction=" in idx[1].lower() and "128" in idx[1], f"Index definition missing tuned parameter ef_construction=128: {idx[1]}"

    
    # 3. Verify index status is valid (not indisvalid = false)
    cur.execute("""
        SELECT i.indisvalid, i.indisready
        FROM pg_index i
        JOIN pg_class c ON c.oid = i.indexrelid
        WHERE c.relname = 'idx_documents_embedding_hnsw';
    """)
    status = cur.fetchone()
    assert status is not None, "Could not fetch index status from pg_index"
    assert status[0] is True, "HNSW index 'idx_documents_embedding_hnsw' is marked invalid (indisvalid = false)"
    assert status[1] is True, "HNSW index 'idx_documents_embedding_hnsw' is not ready (indisready = false)"
    cur.close()


def test_hnsw_index_explain_analyze_usage(db_conn):
    """
    Requirement 1: Verify EXPLAIN ANALYZE query plan uses the HNSW index (not Seq Scan).
    """
    skip_if_no_db()
    cur = db_conn.cursor()
    
    # Ensure there is at least some data in documents
    cur.execute("SELECT COUNT(*) FROM documents;")
    count = cur.fetchone()[0]
    
    query_vector = "[" + ",".join(map(str, generate_random_vector(1024))) + "]"
    
    # Use session SET (or transaction block) so setting persists across commands
    cur.execute("SET enable_seqscan = off;")
    
    try:
        cur.execute(
            f"EXPLAIN ANALYZE SELECT id, content FROM documents ORDER BY embedding <=> %s::vector LIMIT 5;",
            (query_vector,)
        )
        plan_rows = cur.fetchall()
        plan_text = "\n".join([r[0] for r in plan_rows])
    finally:
        cur.execute("SET enable_seqscan = on;")
    
    # Assert plan uses index scan or hnsw index
    has_index_scan = "idx_documents_embedding_hnsw" in plan_text or "Index Scan" in plan_text or "hnsw" in plan_text.lower()
    has_seq_scan = "Seq Scan on documents" in plan_text
    
    assert not (has_seq_scan and not has_index_scan), f"EXPLAIN ANALYZE showed Seq Scan without Index Scan:\n{plan_text}"
    cur.close()
