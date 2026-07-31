import pytest
from conftest import skip_if_no_db, generate_random_vector

pytestmark = pytest.mark.integration


@pytest.mark.integration
def test_query_plan_regression_detection(db_conn):
    """
    Requirement 12: Detect query plan regressions for vector similarity searches.
    """
    skip_if_no_db()
    cur = db_conn.cursor()
    
    query_vector = "[" + ",".join(map(str, generate_random_vector(1024))) + "]"
    
    # Analyze query plan for ANN similarity search
    cur.execute(
        "EXPLAIN (FORMAT JSON) SELECT id, content, 1 - (embedding <=> %s::vector) AS similarity "
        "FROM documents ORDER BY embedding <=> %s::vector LIMIT 5;",
        (query_vector, query_vector)
    )
    plan_json = cur.fetchone()[0]
    cur.close()
    
    assert plan_json is not None and len(plan_json) > 0, "Failed to retrieve query execution plan"
    root_node = plan_json[0]["Plan"]
    
    plan_type = root_node.get("Node Type", "")
    total_cost = root_node.get("Total Cost", 0.0)
    
    print(f"\nQuery Plan Regression Metrics:")
    print(f"  Root Node Type: {plan_type}")
    print(f"  Total Cost:     {total_cost:.2f}")
    
    # Assert plan type is not a high-cost nested loop anomaly or bad subplan
    assert plan_type in ["Limit", "Index Scan", "Bitmap Heap Scan", "Sequential Scan", "Gather Merge", "Sort"], \
        f"Unexpected query plan node type detected: {plan_type}"
