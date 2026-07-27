import os
import sys
import json
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

from app.retrieval.pgvector_client import get_connection  # noqa: E402


def inspect_batches():
    conn = get_connection()
    cur = conn.cursor()

    print("\n" + "=" * 80)
    print("BATCH & EMBEDDING INSPECTION")
    print("=" * 80)

    # -- 1. Embedding dimensions across ALL rows --------------------------------
    print("\n" + "-" * 80)
    print("[1] Embedding dimensions (all rows, grouped)")
    print("-" * 80)

    cur.execute("""
        SELECT vector_dims(embedding) AS dims, count(*)
        FROM documents
        GROUP BY dims;
    """)
    rows = cur.fetchall()
    print(f"  {'Dims':<10} {'Count':>8}")
    print(f"  {'-' * 10} {'-' * 8}")
    for dims, count in rows:
        print(f"  {str(dims):<10} {count:>8}")
    if len(rows) == 1:
        print(f"\n  All rows share the same dimension: {rows[0][0]}")
    else:
        print(f"\n  WARNING: Multiple embedding dimensions detected!")

    # -- 2. Chunk length distribution (rag-book.pdf only) -----------------------
    print("\n" + "-" * 80)
    print("[2] Chunk length distribution (source=/tmp/rag-book.pdf, top 15)")
    print("-" * 80)

    cur.execute("""
        SELECT length(content) AS len, count(*)
        FROM documents
        WHERE metadata->>'source' = '/tmp/rag-book.pdf'
        GROUP BY len
        ORDER BY count(*) DESC
        LIMIT 15;
    """)
    rows = cur.fetchall()
    print(f"  {'Content Length':<16} {'Count':>8}")
    print(f"  {'-' * 16} {'-' * 8}")
    for content_len, count in rows:
        print(f"  {content_len:<16} {count:>8}")

    # Also show min/max/avg/stddev for fuller picture
    cur.execute("""
        SELECT MIN(length(content)), MAX(length(content)),
               ROUND(AVG(length(content))), ROUND(STDDEV(length(content)))
        FROM documents
        WHERE metadata->>'source' = '/tmp/rag-book.pdf';
    """)
    min_len, max_len, avg_len, stddev_len = cur.fetchone()
    print(f"\n  Min: {min_len}  Max: {max_len}  Avg: {avg_len}  StdDev: {stddev_len}")

    # -- 3. ID gap check (ids 15-683) -------------------------------------------
    print("\n" + "-" * 80)
    print("[3] ID gap check: rows between id 15 and 683")
    print("-" * 80)

    cur.execute("""
        SELECT count(*) FROM documents WHERE id BETWEEN 15 AND 683;
    """)
    gap_count = cur.fetchone()[0]
    print(f"  Rows in id range 15-683: {gap_count}")

    if gap_count > 0:
        cur.execute("""
            SELECT id, LEFT(content, 60)
            FROM documents
            WHERE id BETWEEN 15 AND 683
            LIMIT 5;
        """)
        rows = cur.fetchall()
        print(f"\n  Sample rows:")
        for row_id, preview in rows:
            print(f"    id={row_id}: {preview!r}")
    else:
        print("  Confirmed: ID gap 15-683 has NO rows (deleted or skipped sequence values).")

    print("\n" + "=" * 80)
    print("INSPECTION COMPLETE")
    print("=" * 80 + "\n")

    cur.close()
    conn.close()


if __name__ == "__main__":
    inspect_batches()
