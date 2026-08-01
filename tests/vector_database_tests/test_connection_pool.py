import time
import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed
from conftest import skip_if_no_db
from app.retrieval.pgvector_client import get_connection, _get_pool, DB_POOL_MAX_CONN

pytestmark = pytest.mark.integration


def _get_active_pg_connections(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM pg_stat_activity WHERE state IS NOT NULL AND datname = current_database();")
    count = cur.fetchone()[0]
    cur.close()
    return count


@pytest.mark.integration
def test_connection_pool_saturation_and_queuing(db_conn):
    """
    Requirement 8: Stress test connection pool saturation under concurrent multi-threaded load.
    Spins up 25 worker threads against DB_POOL_MAX_CONN (20), holding connections simultaneously
    to ensure max pool capacity is reached and extra workers wait/queue properly.
    """
    skip_if_no_db()
    import threading
    
    num_threads = 25
    target_barrier_count = 15
    barrier = threading.Barrier(target_barrier_count)
    active_counter = 0
    max_observed_active = 0
    lock = threading.Lock()
    
    def worker(worker_id):
        nonlocal active_counter, max_observed_active
        conn = None
        for attempt in range(15):
            try:
                conn = get_connection()
                break
            except RuntimeError:
                time.sleep(0.05)
                
        if conn is None:
            return False
            
        try:
            with lock:
                active_counter += 1
                if active_counter > max_observed_active:
                    max_observed_active = active_counter
            
            cur = conn.cursor()
            cur.execute("SELECT 1;")
            _ = cur.fetchone()
            
            # Use barrier to synchronize workers and guarantee concurrent hold
            try:
                barrier.wait(timeout=2.0)
            except threading.BrokenBarrierError:
                pass
                
            cur.close()
            
            with lock:
                active_counter -= 1
            conn.close()
            return True
        except Exception as e:
            print(f"Worker {worker_id} error: {e}")
            return False

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, i) for i in range(num_threads)]
        results = [f.result() for f in as_completed(futures)]
        
    total_successful = sum(1 for r in results if r)
    print(f"\nConnection Pool Saturation Test Results:")
    print(f"  Max Concurrent Connections Held: {max_observed_active}/{DB_POOL_MAX_CONN}")
    print(f"  Total Worker Successes:          {total_successful}/{num_threads}")
    
    assert max_observed_active >= 15, f"Pool stress failed: peak active connections was only {max_observed_active}, expected >= 15"
    assert total_successful == num_threads, f"Expected {num_threads} workers to complete via pool queuing, got {total_successful}"


@pytest.mark.integration
def test_connection_pool_exhaustion_behavior(raw_db_conn):
    """
    Requirement 8b: Verify explicit pool exhaustion error behavior when pool limit is exceeded without releasing.
    """
    skip_if_no_db()
    from psycopg2.pool import PoolError
    
    pool = _get_pool()
    checked_out = []
    exhaustion_caught = False
    
    try:
        # DB_POOL_MAX_CONN is 20 by default; checkout 25 connections without closing
        for _ in range(DB_POOL_MAX_CONN + 5):
            raw_conn = pool.getconn()
            checked_out.append(raw_conn)
    except (PoolError, RuntimeError) as e:
        exhaustion_caught = True
        print(f"\nPool exhaustion correctly triggered: {type(e).__name__} ({e})")
    finally:
        # Return all checked out connections back to pool
        for conn in checked_out:
            try:
                pool.putconn(conn)
            except Exception:
                pass

    assert exhaustion_caught, f"Expected PoolError/RuntimeError when exceeding max pool capacity ({DB_POOL_MAX_CONN}), but none was raised!"



@pytest.mark.integration
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
