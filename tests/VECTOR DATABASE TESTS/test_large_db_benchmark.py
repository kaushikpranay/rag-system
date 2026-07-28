import time
import pytest
import numpy as np
from conftest import skip_if_no_db, generate_random_vector

def measure_query_latency_percentiles(conn, num_queries=20, top_k=5):
    cur = conn.cursor()
    latencies = []
    
    for _ in range(num_queries):
        query_vector = "[" + ",".join(map(str, generate_random_vector(1024))) + "]"
        start_t = time.time()
        cur.execute(
            "SELECT id, content FROM documents ORDER BY embedding <=> %s::vector LIMIT %s;",
            (query_vector, top_k)
        )
        _ = cur.fetchall()
        elapsed_ms = (time.time() - start_t) * 1000.0
        latencies.append(elapsed_ms)
        
    cur.close()
    
    if not latencies:
        return {"avg": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0}
        
    return {
        "avg": float(np.mean(latencies)),
        "p50": float(np.percentile(latencies, 50)),
        "p95": float(np.percentile(latencies, 95)),
        "p99": float(np.percentile(latencies, 99))
    }


def test_large_database_benchmark(db_conn):
    """
    Requirement 13: Benchmark vector search performance, reporting P50/P95/P99 latency & active document count.
    """
    skip_if_no_db()
    cur = db_conn.cursor()
    cur.execute("SELECT COUNT(*) FROM documents WHERE embedding IS NOT NULL;")
    vector_count = cur.fetchone()[0]
    cur.close()
    
    metrics = measure_query_latency_percentiles(db_conn, num_queries=15, top_k=5)
    
    print(f"\nVector Database Performance Benchmark ({vector_count:,} total vectors):")
    print(f"  Average Latency: {metrics['avg']:.2f} ms")
    print(f"  P50 Latency:     {metrics['p50']:.2f} ms")
    print(f"  P95 Latency:     {metrics['p95']:.2f} ms")
    print(f"  P99 Latency:     {metrics['p99']:.2f} ms")
    
    # Assert query latencies are within reasonable bounds (e.g., P95 < 2500ms)
    assert metrics["p95"] < 2500.0, f"P95 latency ({metrics['p95']:.2f} ms) exceeded SLA threshold 2500ms"
