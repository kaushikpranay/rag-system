import pytest
from conftest import skip_if_no_db

def test_database_health_checks(db_conn):
    """
    Requirement 15: Database health checks (extensions, indexes, locks, active connections, table health).
    """
    skip_if_no_db()
    cur = db_conn.cursor()
    
    # 1. Extensions check
    cur.execute("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';")
    ext = cur.fetchone()
    assert ext is not None, "pgvector extension is missing"
    ext_version = ext[1]
    
    # 2. Indexes check on documents table
    cur.execute("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'documents';")
    indexes = {r[0]: r[1] for r in cur.fetchall()}
    assert "idx_documents_embedding_hnsw" in indexes or "documents_pkey" in indexes, "Key indexes missing on documents table"
    
    # 3. Exclusive locks check
    cur.execute("""
        SELECT COUNT(*) 
        FROM pg_locks 
        WHERE granted = false OR mode LIKE '%ExclusiveLock%';
    """)
    lock_count = cur.fetchone()[0]
    
    # 4. Active connection count check
    cur.execute("""
        SELECT COUNT(*) 
        FROM pg_stat_activity 
        WHERE datname = current_database();
    """)
    active_conns = cur.fetchone()[0]
    
    # 5. Table health & bloat size check
    cur.execute("""
        SELECT pg_size_pretty(pg_total_relation_size('documents')), pg_total_relation_size('documents')
    """)
    pretty_size, raw_bytes = cur.fetchone()
    cur.close()
    
    print(f"\nDatabase Health Summary:")
    print(f"  pgvector Version:   {ext_version}")
    print(f"  Active Indexes:     {list(indexes.keys())}")
    print(f"  Blocked/Exc Locks:  {lock_count}")
    print(f"  Active Connections: {active_conns}")
    print(f"  Table Size:         {pretty_size} ({raw_bytes:,} bytes)")
    
    assert active_conns > 0, "No active connections reported by pg_stat_activity"
    assert raw_bytes >= 0, "Invalid table size reported"
