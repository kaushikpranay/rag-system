import os
import sys
import json
import logging
import socket

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# ---------------------------------------------------------------------------
# SSH Tunnel support: The RDS instance is in a private VPC and not publicly
# accessible.  When running locally, an SSH tunnel must be open:
#
#   ssh -i <key>.pem -N -L 15432:<RDS_HOST>:5432 ec2-user@<EC2_PUBLIC_IP>
#
# We detect the tunnel automatically and re-point the connection to localhost.
# ---------------------------------------------------------------------------
TUNNEL_LOCAL_PORT = int(os.getenv("TUNNEL_LOCAL_PORT", "15432"))

def _tunnel_is_open(port: int = TUNNEL_LOCAL_PORT) -> bool:
    """Return True if something is listening on localhost:<port>."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0

if _tunnel_is_open():
    os.environ["RDS_HOST"] = "127.0.0.1"
    os.environ["RDS_PORT"] = str(TUNNEL_LOCAL_PORT)
    print(f"[tunnel] Detected SSH tunnel on localhost:{TUNNEL_LOCAL_PORT} — routing DB traffic through it.")
else:
    # Check if the RDS host is directly reachable (e.g. running on EC2 in the same VPC)
    rds_host = os.getenv("RDS_HOST", "localhost")
    rds_port = int(os.getenv("RDS_PORT", "5432"))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(5)
        if s.connect_ex((rds_host, rds_port)) != 0:
            print(
                f"\n*** ERROR: Cannot reach RDS at {rds_host}:{rds_port} and no SSH tunnel found on localhost:{TUNNEL_LOCAL_PORT}.\n"
                f"*** Start a tunnel first:\n"
                f"***   ssh -i <key>.pem -N -L {TUNNEL_LOCAL_PORT}:{rds_host}:5432 ec2-user@<EC2_PUBLIC_IP>\n"
            )
            sys.exit(1)

from app.retrieval.pgvector_client import retrieve_similar  # noqa: E402 — must import AFTER env override

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def measure_thresholds():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    golden_set_path = os.path.join(script_dir, "golden_set.json")
    results_path = os.path.join(script_dir, "threshold_results.json")

    if not os.path.exists(golden_set_path):
        logger.error(f"Golden set file not found at {golden_set_path}")
        sys.exit(1)

    with open(golden_set_path, "r", encoding="utf-8") as f:
        golden_set = json.load(f)

    logger.info(f"Loaded {len(golden_set)} queries from {golden_set_path}")

    query_results = []
    correct_similarities = []
    top_wrong_similarities = []
    miss_count = 0

    print("\n" + "=" * 80)
    print("RUNNING RETRIEVAL THRESHOLD EVALUATION")
    print("=" * 80)

    for idx, item in enumerate(golden_set, 1):
        query = item["query"]
        expected_substring = item["expected_chunk_substring"]

        results = retrieve_similar(query, top_k=15, min_similarity=0.0)

        correct_chunk = None
        correct_rank = None
        correct_sim = None
        top_wrong_sim = None

        correct_rerank_score = None
        top_wrong_rerank_score = None

        for rank, res in enumerate(results, 1):
            content = res.get("content", "")
            sim = float(res.get("similarity", 0.0))
            r_score = float(res.get("rerank_score", 0.0))

            if expected_substring in content:
                if correct_chunk is None:
                    correct_chunk = res
                    correct_rank = rank
                    correct_sim = sim
                    correct_rerank_score = r_score
            else:
                if top_wrong_sim is None:
                    top_wrong_sim = sim
                    top_wrong_rerank_score = r_score

        if correct_rank is not None:
            status = "HIT"
            correct_similarities.append(correct_sim)
            logger.info(
                f"[{idx:02d}/{len(golden_set):02d}] HIT  | Rank: {correct_rank:2d} | "
                f"Correct Sim: {correct_sim:.4f} (Rerank: {correct_rerank_score:.4f}) | "
                f"Top Wrong Sim: {top_wrong_sim:.4f} (Rerank: {top_wrong_rerank_score if top_wrong_rerank_score is not None else 'N/A'})"
            )
            print(f"Query: \"{query}\"")
            print(f"  -> Rank: {correct_rank} | Correct Sim: {correct_sim:.4f} (Rerank Score: {correct_rerank_score:.4f}) | Top-1 Wrong Sim: {top_wrong_sim:.4f} (Rerank Score: {top_wrong_rerank_score})\n")
        else:
            status = "MISS"
            miss_count += 1
            logger.warning(
                f"[{idx:02d}/{len(golden_set):02d}] MISS | Correct chunk not found in top 15 | "
                f"Top Wrong Sim: {top_wrong_sim if top_wrong_sim is not None else 'N/A'}"
            )
            print(f"Query: \"{query}\"")
            print(f"  -> MISS | Top-1 Wrong Similarity: {top_wrong_sim}\n")

        if top_wrong_sim is not None:
            top_wrong_similarities.append(top_wrong_sim)

        query_results.append({
            "query": query,
            "expected_chunk_substring": expected_substring,
            "status": status,
            "correct_rank": correct_rank,
            "correct_similarity": correct_sim,
            "top_wrong_similarity": top_wrong_sim
        })

    avg_correct_sim = sum(correct_similarities) / len(correct_similarities) if correct_similarities else 0.0
    min_correct_sim = min(correct_similarities) if correct_similarities else 0.0
    avg_top_wrong_sim = sum(top_wrong_similarities) / len(top_wrong_similarities) if top_wrong_similarities else 0.0

    summary = {
        "total_queries": len(golden_set),
        "hit_count": len(golden_set) - miss_count,
        "miss_count": miss_count,
        "avg_correct_similarity": avg_correct_sim,
        "min_correct_similarity": min_correct_sim,
        "avg_top_wrong_similarity": avg_top_wrong_sim
    }

    output_data = {
        "summary": summary,
        "details": query_results
    }

    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print("THRESHOLD EVALUATION SUMMARY")
    print("=" * 80)
    print(f"Total Queries Evaluated:          {len(golden_set)}")
    print(f"Hits (Found in Top 15):           {summary['hit_count']}")
    print(f"Misses:                           {miss_count}")
    print(f"Avg Similarity of Correct Chunks: {avg_correct_sim:.4f}")
    print(f"Min Similarity of Correct Chunks: {min_correct_sim:.4f}")
    print(f"Avg Similarity of Top Wrong Chunks: {avg_top_wrong_sim:.4f}")
    print("=" * 80)
    print(f"\nDetailed results saved to {results_path}\n")

if __name__ == "__main__":
    measure_thresholds()
