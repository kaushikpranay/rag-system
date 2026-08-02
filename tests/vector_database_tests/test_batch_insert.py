import json
import time
import pytest
import hashlib
from psycopg2.extras import execute_values
from conftest import skip_if_no_db, generate_random_vector

pytestmark = pytest.mark.integration


@pytest.mark.integration
def test_batch_insert_validation_execute_values(db_conn):
    """
    Requirement 10: Validate batch insert using execute_values and verify throughput & deduplication.
    """
    skip_if_no_db()
    
    num_items = 20
    test_prefix = f"batch_test_{int(time.time())}"
    
    tuples_to_insert = []
    hashes = []
    for i in range(num_items):
        content = f"Batch insert test document content {test_prefix}_{i}"
        chash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        hashes.append(chash)
        metadata = json.dumps({"source": "batch_test", "content_hash": chash, "test_run": test_prefix})
        vec = generate_random_vector(1024)
        tuples_to_insert.append((content, metadata, vec))
        
    cur = db_conn.cursor()
    
    query = """
        INSERT INTO documents (content, metadata, embedding)
        VALUES %s
        ON CONFLICT ((metadata->>'content_hash')) DO NOTHING
        RETURNING id;
    """
    
    start_time = time.time()
    inserted_rows = execute_values(cur, query, tuples_to_insert, fetch=True)
    elapsed = time.time() - start_time
    
    inserted_count = len(inserted_rows) if inserted_rows else 0
    assert inserted_count == num_items, f"Expected {num_items} inserted rows, got {inserted_count}"
    
    # Test ON CONFLICT DO NOTHING by re-inserting identical batch
    dup_inserted = execute_values(cur, query, tuples_to_insert, fetch=True)
    dup_count = len(dup_inserted) if dup_inserted else 0
    assert dup_count == 0, f"Expected 0 inserted rows for duplicate batch, got {dup_count}"
    
    # Clean up test rows
    cur.execute("DELETE FROM documents WHERE metadata->>'test_run' = %s;", (test_prefix,))
    cur.close()
    
    print(f"\nBatch Insert Benchmark:")
    print(f"  Inserted {num_items} rows in {elapsed:.4f}s ({num_items / elapsed:.2f} rows/sec)")


@pytest.mark.integration
def test_transaction_rollback_and_recovery(db_conn):
    """
    Requirement 11: Validate transaction rollback and database recovery on failure.
    """
    skip_if_no_db()
    
    test_prefix = f"rollback_test_{int(time.time())}"
    content = f"Rollback test document {test_prefix}"
    chash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    metadata = json.dumps({"source": "rollback_test", "content_hash": chash, "test_run": test_prefix})
    vec = generate_random_vector(1024)
    
    # Set autocommit to False on underlying connection for explicit transaction control
    raw_conn = getattr(db_conn, "_conn", db_conn)
    raw_conn.autocommit = False
    cur = raw_conn.cursor()
    
    try:
        # Step 1: Valid insert
        cur.execute(
            "INSERT INTO documents (content, metadata, embedding) VALUES (%s, %s, %s);",
            (content, metadata, vec)
        )
        
        # Step 2: Intentional error (violating NOT NULL constraint)
        cur.execute("INSERT INTO documents (id, content) VALUES (NULL, NULL);")
        raw_conn.commit()
    except Exception:
        raw_conn.rollback()
    finally:
        raw_conn.autocommit = True
        cur.close()
        
    # Verify Step 1 insert was rolled back completely
    cur = db_conn.cursor()
    cur.execute("SELECT COUNT(*) FROM documents WHERE metadata->>'test_run' = %s;", (test_prefix,))
    count = cur.fetchone()[0]
    cur.close()
    
    assert count == 0, f"Transaction rollback failed! Found {count} rows that should have been rolled back"
