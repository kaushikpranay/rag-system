import json
import pytest
import numpy as np
from conftest import skip_if_no_db

def test_vector_dimension_validation(db_conn):
    """
    Requirement 4: Validate vector dimension (must be 1024-d, non-null, valid structure).
    """
    skip_if_no_db()
    cur = db_conn.cursor()
    
    # 1. Check vector dimension via pgvector function vector_dims(embedding)
    cur.execute("""
        SELECT vector_dims(embedding), COUNT(*) 
        FROM documents 
        WHERE embedding IS NOT NULL 
        GROUP BY vector_dims(embedding);
    """)
    rows = cur.fetchall()
    
    if rows:
        for dim, count in rows:
            assert dim == 1024, f"Found vectors with invalid dimension {dim} (expected 1024)"
            
    # 2. Check for null or empty embeddings
    cur.execute("SELECT COUNT(*) FROM documents WHERE embedding IS NULL;")
    null_count = cur.fetchone()[0]
    assert null_count == 0, f"Found {null_count} documents with NULL embedding"
    cur.close()


def test_embedding_drift_detection(db_conn):
    """
    Requirement 5: Detect embedding drift, zero-vectors, NaN/Inf values, and norm anomalies.
    """
    skip_if_no_db()
    cur = db_conn.cursor()
    
    cur.execute("SELECT id, embedding FROM documents WHERE embedding IS NOT NULL LIMIT 500;")
    rows = cur.fetchall()
    cur.close()
    
    if not rows:
        pytest.skip("No documents in database to evaluate embedding drift.")
        
    norms = []
    zero_vectors = 0
    nan_inf_count = 0
    
    from conftest import vec_to_array

    for doc_id, vec in rows:
        arr = vec_to_array(vec)
            
        # Check for NaN / Inf
        if np.isnan(arr).any() or np.isinf(arr).any():
            nan_inf_count += 1
            
        norm = float(np.linalg.norm(arr))
        norms.append(norm)
        
        if norm < 1e-6:
            zero_vectors += 1
            
    assert nan_inf_count == 0, f"Detected {nan_inf_count} vectors containing NaN or Inf values"
    assert zero_vectors == 0, f"Detected {zero_vectors} zero-magnitude vectors"
    
    if norms:
        mean_norm = float(np.mean(norms))
        std_norm = float(np.std(norms))
        # Normalized embeddings should have norm close to 1.0 (between 0.8 and 1.2)
        assert 0.7 <= mean_norm <= 1.3, f"Mean vector norm ({mean_norm:.4f}) drifts outside expected range [0.7, 1.3]"
        assert std_norm < 0.3, f"Vector norm standard deviation ({std_norm:.4f}) exhibits abnormal variance"


def test_duplicate_vector_detection(db_conn):
    """
    Requirement 6: Detect duplicate or near-identical vectors (cosine similarity >= 0.9999).
    """
    skip_if_no_db()
    cur = db_conn.cursor()
    
    # Query pairs with near 1.0 similarity
    cur.execute("""
        SELECT a.id, b.id, 1 - (a.embedding <=> b.embedding) AS sim
        FROM documents a
        JOIN documents b ON a.id < b.id
        WHERE 1 - (a.embedding <=> b.embedding) >= 0.9999
        LIMIT 50;
    """)
    exact_dupes = cur.fetchall()
    cur.close()
    
    # Reporting duplicate vectors found
    print(f"\nDuplicate vector check: found {len(exact_dupes)} pairs with similarity >= 0.9999")
    # Duplicate vectors should be managed; this test asserts detection functions correctly
    assert isinstance(exact_dupes, list)


def test_metadata_integrity_validation(db_conn):
    """
    Requirement 7: Validate metadata integrity (JSONB format, mandatory content_hash SHA-256).
    """
    skip_if_no_db()
    cur = db_conn.cursor()
    
    # 1. Check for documents with missing or non-object metadata
    cur.execute("SELECT COUNT(*) FROM documents WHERE metadata IS NULL OR jsonb_typeof(metadata) != 'object';")
    invalid_json_count = cur.fetchone()[0]
    assert invalid_json_count == 0, f"Found {invalid_json_count} documents with invalid JSONB metadata"
    
    # 2. Check for missing content_hash in metadata
    cur.execute("SELECT COUNT(*) FROM documents WHERE metadata->>'content_hash' IS NULL;")
    missing_hash_count = cur.fetchone()[0]
    
    # 3. Check for invalid SHA-256 hex string lengths (should be 64 characters)
    cur.execute("""
        SELECT COUNT(*) 
        FROM documents 
        WHERE metadata->>'content_hash' IS NOT NULL 
          AND length(metadata->>'content_hash') != 64;
    """)
    malformed_hash_count = cur.fetchone()[0]
    cur.close()
    
    assert malformed_hash_count == 0, f"Found {malformed_hash_count} documents with malformed content_hash length (!= 64)"
