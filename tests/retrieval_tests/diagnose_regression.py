import os
import sys
import json
import socket

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# ---------------------------------------------------------------------------
# SSH Tunnel support  (same logic as measure_thresholds.py)
# ---------------------------------------------------------------------------
TUNNEL_LOCAL_PORT = int(os.getenv("TUNNEL_LOCAL_PORT", "15432"))


def _tunnel_is_open(port: int = TUNNEL_LOCAL_PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


if _tunnel_is_open():
    os.environ["RDS_HOST"] = "127.0.0.1"
    os.environ["RDS_PORT"] = str(TUNNEL_LOCAL_PORT)
    print(f"[tunnel] Detected SSH tunnel on localhost:{TUNNEL_LOCAL_PORT} — routing DB traffic through it.")
else:
    rds_host = os.getenv("RDS_HOST", "localhost")
    rds_port = int(os.getenv("RDS_PORT", "5432"))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(5)
        if s.connect_ex((rds_host, rds_port)) != 0:
            print(
                f"\n*** ERROR: Cannot reach RDS at {rds_host}:{rds_port} and no SSH tunnel on localhost:{TUNNEL_LOCAL_PORT}.\n"
                f"*** Start a tunnel first:\n"
                f"***   ssh -i <key>.pem -N -L {TUNNEL_LOCAL_PORT}:{rds_host}:5432 ec2-user@<EC2_PUBLIC_IP>\n"
            )
            sys.exit(1)

from app.retrieval.pgvector_client import get_connection  # noqa: E402


def diagnose():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    golden_path = os.path.join(script_dir, "golden_set.json")

    with open(golden_path, "r", encoding="utf-8") as f:
        golden_set = json.load(f)

    conn = get_connection()
    cur = conn.cursor()

    # ── 1. Total row count ─────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("RETRIEVAL REGRESSION DIAGNOSTICS")
    print("=" * 80)

    cur.execute("SELECT count(*) FROM documents;")
    total_rows = cur.fetchone()[0]
    print(f"\n[1] Total rows in 'documents' table: {total_rows}\n")

    # ── 2. Per-query substring search ──────────────────────────────────────
    print("-" * 80)
    print("[2] Checking if golden-set chunks exist in the database")
    print("-" * 80)

    found_count = 0
    not_found_count = 0

    for idx, item in enumerate(golden_set, 1):
        query = item["query"]
        substring = item["expected_chunk_substring"]
        search_term = substring[:40]
        pattern = f"%{search_term}%"

        cur.execute(
            "SELECT id, metadata->>'source' FROM documents WHERE content ILIKE %s LIMIT 3",
            (pattern,),
        )
        rows = cur.fetchall()

        if rows:
            found_count += 1
            print(f"  [{idx:02d}] FOUND      | Query: \"{query[:70]}...\"")
            for row_id, source in rows:
                print(f"       -> row id={row_id}, source={source}")
        else:
            not_found_count += 1
            print(f"  [{idx:02d}] NOT FOUND  | Query: \"{query[:70]}...\"")
            print(f"       -> searched for: \"{search_term}...\"")

    print(f"\n  Summary: {found_count} FOUND, {not_found_count} NOT FOUND out of {len(golden_set)} entries\n")

    # ── 3. Embedding dimensions ────────────────────────────────────────────
    print("-" * 80)
    print("[3] Embedding dimensions (first 5 rows)")
    print("-" * 80)

    cur.execute("SELECT id, vector_dims(embedding) FROM documents WHERE embedding IS NOT NULL LIMIT 5;")
    dim_rows = cur.fetchall()
    if dim_rows:
        for row_id, dims in dim_rows:
            print(f"  row id={row_id}  =>  vector_dims = {dims}")
    else:
        print("  No rows with embeddings found!")

    # ── 4. Null embedding count ────────────────────────────────────────────
    print()
    print("-" * 80)
    print("[4] Rows with NULL embeddings")
    print("-" * 80)

    cur.execute("SELECT count(*) FROM documents WHERE embedding IS NULL;")
    null_count = cur.fetchone()[0]
    print(f"  Rows with NULL embedding: {null_count}  (out of {total_rows} total)")

    print("\n" + "=" * 80)
    print("DIAGNOSTICS COMPLETE")
    print("=" * 80 + "\n")

    cur.close()
    conn.close()


if __name__ == "__main__":
    diagnose()
