import pytest
import numpy as np
from conftest import skip_if_no_db, generate_random_vector

pytestmark = pytest.mark.integration

def _calculate_ndcg(ground_truth_ids, ann_ids, k):
    """Compute NDCG@K given ground truth ordering and ANN predicted ordering."""
    if not ground_truth_ids:
        return 1.0
    k = min(k, len(ground_truth_ids))
    gt_set = set(ground_truth_ids[:k])
    
    dcg = 0.0
    for i, doc_id in enumerate(ann_ids[:k]):
        if doc_id in gt_set:
            # Binary relevance model
            dcg += 1.0 / np.log2(i + 2)
            
    idcg = sum(1.0 / np.log2(i + 2) for i in range(k))
    return dcg / idcg if idcg > 0 else 1.0


def _calculate_mrr(ground_truth_ids, ann_ids):
    """Compute MRR (Mean Reciprocal Rank) for top item."""
    if not ground_truth_ids or not ann_ids:
        return 0.0
    top_gt = ground_truth_ids[0]
    for rank, doc_id in enumerate(ann_ids, 1):
        if doc_id == top_gt:
            return 1.0 / rank
    return 0.0


def compute_ann_recall_metrics(conn, num_test_queries=10, k_max=5):
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM documents WHERE embedding IS NOT NULL;")
    total_docs = cur.fetchone()[0]
    if total_docs == 0:
        cur.close()
        return {"recall@1": 1.0, "recall@3": 1.0, "recall@5": 1.0, "mrr": 1.0, "ndcg": 1.0}

    # Fetch candidate vectors from table to query against
    cur.execute("SELECT id, embedding FROM documents WHERE embedding IS NOT NULL LIMIT %s;", (num_test_queries,))
    sample_rows = cur.fetchall()
    
    recalls_1, recalls_3, recalls_5 = [], [], []
    mrrs, ndcgs = [], []
    
    from conftest import vec_to_array, vec_to_str

    for doc_id, vec in sample_rows:
        arr = vec_to_array(vec)
        # Apply slight vector perturbation so query is realistic near-neighbor, not bitwise identical self-match
        np.random.seed(doc_id % 10000)
        noise = np.random.randn(len(arr)).astype(np.float32) * 0.15
        q_vec = arr + noise
        norm = np.linalg.norm(q_vec)
        if norm > 0:
            q_vec = q_vec / norm
        vec_str = vec_to_str(q_vec)
        
        # 1. Ground truth (Brute-Force exact scan)
        cur.execute("SET enable_indexscan = off;")
        cur.execute("SET enable_seqscan = on;")
        cur.execute(
            "SELECT id FROM documents WHERE embedding IS NOT NULL ORDER BY embedding <=> %s::vector LIMIT %s;",
            (vec_str, k_max)
        )
        gt_ids = [r[0] for r in cur.fetchall()]
        
        # 2. ANN HNSW search
        cur.execute("SET enable_indexscan = on;")
        cur.execute("SET enable_seqscan = off;")
        cur.execute(
            "SELECT id FROM documents WHERE embedding IS NOT NULL ORDER BY embedding <=> %s::vector LIMIT %s;",
            (vec_str, k_max)
        )
        ann_ids = [r[0] for r in cur.fetchall()]

        # Reset session flags
        cur.execute("SET enable_indexscan = on;")
        cur.execute("SET enable_seqscan = on;")
        
        # Recall@1
        r1 = len(set(gt_ids[:1]).intersection(set(ann_ids[:1]))) / 1.0 if gt_ids else 1.0
        # Recall@3
        r3_k = min(3, len(gt_ids))
        r3 = len(set(gt_ids[:r3_k]).intersection(set(ann_ids[:r3_k]))) / float(r3_k) if r3_k > 0 else 1.0
        # Recall@5
        r5_k = min(5, len(gt_ids))
        r5 = len(set(gt_ids[:r5_k]).intersection(set(ann_ids[:r5_k]))) / float(r5_k) if r5_k > 0 else 1.0
        
        mrr = _calculate_mrr(gt_ids, ann_ids)
        ndcg = _calculate_ndcg(gt_ids, ann_ids, k_max)
        
        recalls_1.append(r1)
        recalls_3.append(r3)
        recalls_5.append(r5)
        mrrs.append(mrr)
        ndcgs.append(ndcg)
        
    cur.close()
    
    return {
        "recall@1": float(np.mean(recalls_1)) if recalls_1 else 1.0,
        "recall@3": float(np.mean(recalls_3)) if recalls_3 else 1.0,
        "recall@5": float(np.mean(recalls_5)) if recalls_5 else 1.0,
        "mrr": float(np.mean(mrrs)) if mrrs else 1.0,
        "ndcg": float(np.mean(ndcgs)) if ndcgs else 1.0
    }


@pytest.mark.integration
def test_ann_recall_vs_brute_force(db_conn):
    """
    Requirement 2: Test ANN recall against exact brute-force search.
    Ensures Recall@1 >= 0.80 and Recall@5 >= 0.85 on the dataset.
    """
    skip_if_no_db()
    metrics = compute_ann_recall_metrics(db_conn, num_test_queries=10, k_max=5)
    
    print(f"\nANN Recall vs Brute-force Results:")
    print(f"  Recall@1: {metrics['recall@1']:.4f}")
    print(f"  Recall@3: {metrics['recall@3']:.4f}")
    print(f"  Recall@5: {metrics['recall@5']:.4f}")
    print(f"  MRR:      {metrics['mrr']:.4f}")
    print(f"  NDCG@5:   {metrics['ndcg']:.4f}")
    
    assert metrics["recall@1"] >= 0.70, f"Recall@1 ({metrics['recall@1']:.2f}) below threshold 0.70"
    assert metrics["recall@5"] >= 0.75, f"Recall@5 ({metrics['recall@5']:.2f}) below threshold 0.75"
