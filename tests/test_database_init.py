import pytest
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv(override=True)

from app.retrieval.pgvector_client import get_connection, init_db

def test_database_schema_and_connection():
    rds_host = os.getenv("RDS_HOST", "localhost")
    try:
        conn_test = psycopg2.connect(
            host=rds_host,
            port=os.getenv("RDS_PORT", 5432),
            dbname=os.getenv("RDS_DB", "ragdb"),
            user=os.getenv("RDS_USER", "ragadmin"),
            password=os.getenv("RDS_PASSWORD", ""),
            connect_timeout=3
        )
        conn_test.close()
    except psycopg2.OperationalError:
        pytest.skip(f"Database at {rds_host} is not reachable in this environment (e.g. CI runner)")

    # Ensure init_db runs cleanly
    init_db()
    
    conn = get_connection()
    assert conn is not None
    
    cur = conn.cursor()
    
    # Verify extension 'vector' is installed
    cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector';")
    ext = cur.fetchone()
    assert ext is not None, "pgvector extension is missing in database"
    assert ext[0] == "vector"
    
    # Verify 'documents' table exists
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name='documents';")
    tbl = cur.fetchone()
    assert tbl is not None, "documents table is missing in database"
    
    # Verify columns in 'documents' table
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_schema='public' AND table_name='documents';
    """)
    cols = [r[0] for r in cur.fetchall()]
    for expected_col in ["id", "content", "metadata", "embedding", "created_at"]:
        assert expected_col in cols, f"Column {expected_col} missing in documents table"
        
    cur.close()
    conn.close()
