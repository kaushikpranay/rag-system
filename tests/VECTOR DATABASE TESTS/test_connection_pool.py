import time
import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed
from conftest import skip_if_no_db
from app.retrieval.pgvector_client import get_connection, _get_pool

def _get_active_pg_connections(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM pg_stat_activity WHERE state IS NOT NULL AND datname = current_database();")
    count = cur.fetchone()[0]
    cur.close()
    return count


def test_connection_pool_stress(db_conn):
    """
    Requirement 8: Stress test connection pool under concurrent multi-threaded load.
    """
    skip_if_no_db()
    
    num_threads = 15
    num_iterations_per_thread = 5
    
    def worker(worker_id):
        successes = 0
        for _ in range(num_iterations_per_thread):
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("SELECT 1;")
                res = cur.fetchone()
                cur.close()
                conn.close()
                if res and res[0] == 1:
                    successes += 1
            except Exception as e:
                print(f"Worker {worker_id} error: {e}")
        return successes

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, i) for i in range(num_threads)]
        results = [f.result() for f in as_completed(futures)]
        
    total_successful = sum(results)
    expected_total = num_threads * num_iterations_per_thread
    assert total_successful == expected_total, f"Expected {expected_total} successful connection acquisitions, got {total_successful}"


def test_connection_leak_detection_pg_stat_activity(raw_db_conn):
    """
    Requirement 9: Detect connection leaks by inspecting pg_stat_activity before and after pool activity.
    """
    skip_if_no_db()
    
    initial_connections = _get_active_pg_connections(raw_db_conn)
    
    # Perform multiple connection acquisitions and closes
    for _ in range(20):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        cur.close()
        conn.close()
        
    time.sleep(0.5) # allow pool cleanup
    
    final_connections = _get_active_pg_connections(raw_db_conn)
    
    delta = final_connections - initial_connections
    print(f"\nConnection leak check:")
    print(f"  Initial active connections: {initial_connections}")
    print(f"  Final active connections:   {final_connections}")
    print(f"  Delta:                       {delta}")
    
    # Delta should not grow continuously (allow small tolerance for pool min connection growth)
    assert delta <= 5, f"Possible connection leak detected! Active connections grew by {delta}"
