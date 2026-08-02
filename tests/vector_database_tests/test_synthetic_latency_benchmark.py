import time
import pytest
import numpy as np
from conftest import skip_if_no_db, generate_random_vector

import os

def measure_query_latency_percentiles(conn, num_queries=20, top_k=5):
    cur = conn.cursor()
    latencies = []
    
    for _ in range(num_queries):
        query_vector = "[" + ",".join(map(str, generate_random_vector(1024))) + "]"
        start_t = time.time()
        cur.execute(
            "SELECT id, content FROM documents_benchmark ORDER BY embedding <=> %s::vector, id ASC LIMIT %s;",
            (query_vector, top_k)
        )
        _ = cur.fetchall()
        elapsed_ms = (time.time() - start_t) * 1000.0
        latencies.append(elapsed_ms)
        
    cur.close()
    
    if not latencies:
        return {"min": 0.0, "p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0, "avg": 0.0}
        
    return {
        "min": float(np.min(latencies)),
        "p50": float(np.percentile(latencies, 50)),
        "p90": float(np.percentile(latencies, 90)),
        "p95": float(np.percentile(latencies, 95)),
        "p99": float(np.percentile(latencies, 99)),
        "max": float(np.max(latencies)),
        "avg": float(np.mean(latencies))
    }


TARGET_VECTOR_COUNT_FULL = 100000
TARGET_VECTOR_COUNT_FAST = 5000

pytestmark = pytest.mark.integration


@pytest.mark.integration
def test_synthetic_latency_benchmark(db_conn):
    """
    Synthetic isolated latency benchmark — measures HNSW query latency against a
    separate `documents_benchmark` table populated with random vectors.

    NOTE: This does NOT benchmark production data (the ~820-row `documents` table).
    It exercises pgvector/HNSW index performance in isolation with synthetic vectors.

    Execution Modes:
    - Full Scale Mode (Default): Populates to 100,000 synthetic vectors.
    - Fast / CI Mode (`FAST_BENCHMARK=1`): Limits to 5,000 synthetic vectors.
    """
    skip_if_no_db()
    import sys
    
    is_fast_mode = os.getenv("FAST_BENCHMARK") == "1" or "--fast" in sys.argv
    target_count = TARGET_VECTOR_COUNT_FAST if is_fast_mode else TARGET_VECTOR_COUNT_FULL
    
    cur = db_conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS documents_benchmark (
            id BIGSERIAL PRIMARY KEY,
            content TEXT NOT NULL,
            metadata JSONB DEFAULT '{}',
            embedding VECTOR(1024),
            created_at TIMESTAMPTZ DEFAULT now()
        );
    """)
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_benchmark_content_hash ON documents_benchmark ((metadata->>'content_hash'));")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_documents_benchmark_embedding_hnsw ON documents_benchmark USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 128);")
    
    cur.execute("SELECT COUNT(*) FROM documents_benchmark;")
    current_count = cur.fetchone()[0]
    
    if current_count < target_count:
        from psycopg2.extras import execute_values
        needed = target_count - current_count
        print(f"\n[LATENCY BENCHMARK] Populating database with {needed:,} synthetic vectors (target: {target_count:,})...")
        batch_size = 5000
        for b in range(0, needed, batch_size):
            count_to_add = min(batch_size, needed - b)
            tuples = []
            for i in range(count_to_add):
                v = generate_random_vector(1024)
                v_str = "[" + ",".join(map(str, v)) + "]"
                tuples.append((f"Synthetic benchmark document {b + i}", f'{{"source": "synthetic_100k", "content_hash": "syn100k_{current_count + b + i}"}}', v_str))
            query = "INSERT INTO documents_benchmark (content, metadata, embedding) VALUES %s ON CONFLICT ((metadata->>'content_hash')) DO NOTHING"
            execute_values(cur, query, tuples, template="(%s, %s, %s::vector)")

    cur.execute("SELECT COUNT(*) FROM documents_benchmark WHERE embedding IS NOT NULL;")
    vector_count = cur.fetchone()[0]
    cur.close()
    
    host = os.getenv("RDS_HOST", "127.0.0.1")
    port = os.getenv("RDS_PORT", "5432")
    host_type = "Local PostgreSQL / SSH Tunnel" if host in ("127.0.0.1", "localhost") else "Remote AWS RDS Instance"
    
    metrics = measure_query_latency_percentiles(db_conn, num_queries=20, top_k=5)
    
    print(f"\n=======================================================")
    print(f"[LATENCY BENCHMARK] Target Host: {host}:{port} ({host_type})")
    print(f"[LATENCY BENCHMARK] Active Vectors: {vector_count:,}")
    print(f"=======================================================")
    print(f"  Min Latency:     {metrics['min']:.2f} ms")
    print(f"  P50 Latency:     {metrics['p50']:.2f} ms")
    print(f"  P90 Latency:     {metrics['p90']:.2f} ms")
    print(f"  P95 Latency:     {metrics['p95']:.2f} ms")
    print(f"  P99 Latency:     {metrics['p99']:.2f} ms")
    print(f"  Max Latency:     {metrics['max']:.2f} ms")
    print(f"  Avg Latency:     {metrics['avg']:.2f} ms")
    
    # Assert query latencies are within reasonable bounds (e.g., P95 < 2500ms)
    assert metrics["p95"] < 2500.0, f"P95 latency ({metrics['p95']:.2f} ms) exceeded SLA threshold 2500ms"


