import os
import sys
import json
import math
import socket

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# ---------------------------------------------------------------------------
# SSH Tunnel support
# ---------------------------------------------------------------------------
TUNNEL_LOCAL_PORT = int(os.getenv("TUNNEL_LOCAL_PORT", "15432"))


def _tunnel_is_open(port: int = TUNNEL_LOCAL_PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


if _tunnel_is_open():
    os.environ["RDS_HOST"] = "127.0.0.1"
    os.environ["RDS_PORT"] = str(TUNNEL_LOCAL_PORT)
    print(f"[tunnel] Detected SSH tunnel on localhost:{TUNNEL_LOCAL_PORT}")
else:
    rds_host = os.getenv("RDS_HOST", "localhost")
    rds_port = int(os.getenv("RDS_PORT", "5432"))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(5)
        if s.connect_ex((rds_host, rds_port)) != 0:
            print(
                f"\n*** ERROR: Cannot reach RDS at {rds_host}:{rds_port} "
                f"and no SSH tunnel on localhost:{TUNNEL_LOCAL_PORT}.\n"
                f"*** Start a tunnel first:\n"
                f"***   ssh -i <key>.pem -N -L {TUNNEL_LOCAL_PORT}:{rds_host}:5432 ec2-user@<EC2_PUBLIC_IP>\n"
            )
            sys.exit(1)

from app.retrieval.pgvector_client import get_connection, get_bedrock_embedding  # noqa: E402


def parse_vector(val):
    if val is None:
        return []
    if isinstance(val, str):
        return json.loads(val)
    if hasattr(val, "tolist"):
        return val.tolist()
    if hasattr(val, "to_numpy"):
        return val.to_numpy().tolist()
    s = str(val)
    if s.startswith("[") and s.endswith("]"):
        return json.loads(s)
    return [float(x) for x in val]


def cosine_similarity(v1, v2):
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def verify_embedding_integrity():
    conn = get_connection()
    cur = conn.cursor()

    print("\n" + "=" * 70)
    print("VERIFYING EMBEDDING INTEGRITY")
    print("=" * 70)

    # 1. Pick 5 random rows from documents
    print("\n[1] Comparing Stored vs. Fresh Bedrock Embeddings for 5 Random Rows...")
    cur.execute("SELECT id, content, embedding::text FROM documents ORDER BY RANDOM() LIMIT 5;")
    rows = cur.fetchall()

    for row_id, content, stored_embedding_raw in rows:
        stored_vec = parse_vector(stored_embedding_raw)

        # Re-compute embedding fresh via Bedrock API using identical get_bedrock_embedding function
        fresh_vec = get_bedrock_embedding(content)

        sim = cosine_similarity(stored_vec, fresh_vec)
        preview = content[:60].replace("\n", " ")
        
        stored_fmt = [round(x, 6) for x in stored_vec[:5]] if stored_vec else []
        fresh_fmt = [round(x, 6) for x in fresh_vec[:5]] if fresh_vec else []

        print(f"\n  Row ID: {row_id}")
        print(f"    Content: {preview!r}")
        print(f"    Stored Vec  (len={len(stored_vec)}): {stored_fmt}")
        print(f"    Fresh Vec   (len={len(fresh_vec)}): {fresh_fmt}")
        print(f"    Cosine Similarity: {sim:.6f}")

    # 2. Check for zero-vectors or NaN/Inf values
    print("\n[2] Checking all document embeddings for Zero Vectors or Invalid (NaN/Inf) Values...")
    cur.execute("SELECT id, embedding::text FROM documents;")
    all_rows = cur.fetchall()

    zero_vector_count = 0
    invalid_value_count = 0

    for row_id, embedding_raw in all_rows:
        vec = parse_vector(embedding_raw)

        if not vec:
            continue

        # Check for zero vector
        if all(x == 0.0 for x in vec):
            zero_vector_count += 1

        # Check for NaN / Inf
        if any(math.isnan(x) or math.isinf(x) for x in vec):
            invalid_value_count += 1

    print(f"  Total Document Rows Evaluated: {len(all_rows)}")
    print(f"  Rows with All-Zero Vectors:    {zero_vector_count}")
    print(f"  Rows with NaN/Inf Values:      {invalid_value_count}")

    print("\n" + "=" * 70)
    print("INTEGRITY VERIFICATION COMPLETE")
    print("=" * 70 + "\n")

    cur.close()
    conn.close()


if __name__ == "__main__":
    verify_embedding_integrity()
