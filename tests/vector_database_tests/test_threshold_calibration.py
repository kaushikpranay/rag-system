import os
import json
import pytest
import numpy as np
from conftest import skip_if_no_db

def calibrate_similarity_thresholds(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM documents WHERE embedding IS NOT NULL;")
    total = cur.fetchone()[0]
    
    if total == 0:
        cur.close()
        return {"recommended_threshold": 0.35, "f1_table": {}}

    # Fetch document embeddings to run similarity threshold sweep
    cur.execute("SELECT id, embedding FROM documents WHERE embedding IS NOT NULL LIMIT 50;")
    rows = cur.fetchall()
    cur.close()

    thresholds = [0.20, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.70]
    
    # Calculate similarity metrics across threshold cutoffs
    # In vector similarity retrieval, true positives are relevant documents above threshold
    results = {}
    best_f1 = -1.0
    recommended_thresh = 0.35

    cur = conn.cursor()
    
    from conftest import vec_to_array, vec_to_str

    for th in thresholds:
        tp, fp, fn, tn = 0, 0, 0, 0
        for doc_id, vec in rows[:25]:
            arr = vec_to_array(vec)
            np.random.seed(doc_id % 10000)
            variance = 0.04 + (doc_id % 5) * 0.02
            noise = np.random.randn(len(arr)).astype(np.float32) * variance
            q_vec = arr + noise
            norm = np.linalg.norm(q_vec)
            if norm > 0:
                q_vec = q_vec / norm
            vec_str = vec_to_str(q_vec)

            cur.execute("""
                SELECT id, 1 - (embedding <=> %s::vector) AS sim 
                FROM documents 
                WHERE embedding IS NOT NULL 
                ORDER BY embedding <=> %s::vector 
                LIMIT 10;
            """, (vec_str, vec_str))
            sims = cur.fetchall()
            
            for rank, (r_id, s) in enumerate(sims):
                is_relevant = (r_id == doc_id) # True matching target document chunk
                is_retrieved = (s >= th)
                
                if is_relevant and is_retrieved:
                    tp += 1
                elif not is_relevant and is_retrieved:
                    fp += 1
                elif is_relevant and not is_retrieved:
                    fn += 1
                else:
                    tn += 1
                    
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        results[str(th)] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4)
        }
        
        if f1 > best_f1:
            best_f1 = f1
            recommended_thresh = th

    cur.close()

    return {
        "recommended_threshold": recommended_thresh,
        "best_f1": best_f1,
        "threshold_grid": results
    }


pytestmark = pytest.mark.integration


@pytest.mark.integration
def test_threshold_calibration(db_conn):
    """
    Requirement 14: Threshold calibration calculating Precision, Recall, F1 and recommended threshold.
    """
    skip_if_no_db()
    calib = calibrate_similarity_thresholds(db_conn)
    
    print(f"\nThreshold Calibration Results:")
    print(f"  Recommended Threshold: {calib['recommended_threshold']}")
    print(f"  Best F1 Score:         {calib['best_f1']:.4f}")
    print(f"  Threshold Grid:")
    for th, metrics in calib["threshold_grid"].items():
        print(f"    Thresh {th}: Precision={metrics['precision']}, Recall={metrics['recall']}, F1={metrics['f1']}")
        
    assert calib["recommended_threshold"] is not None
    assert 0.0 <= calib["recommended_threshold"] <= 1.0
