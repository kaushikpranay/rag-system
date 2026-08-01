import os
import sys
import json
import socket
import textwrap
import hashlib

# Force UTF-8 output -- DB content (from PDFs) contains Unicode chars
# that the default Windows cp1252 console encoding cannot handle.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

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


def inspect():
    conn = get_connection()
    cur = conn.cursor()

    print("\n" + "=" * 80)
    print("DUPLICATE & INGESTION INSPECTION")
    print("=" * 80)

    # ── 1. Total vs distinct content (compute hash on the fly) ─────────────
    print("\n" + "-" * 80)
    print("[1] Row count vs distinct content")
    print("-" * 80)

    cur.execute("SELECT count(*) FROM documents;")
    total = cur.fetchone()[0]

    cur.execute("SELECT count(DISTINCT md5(content)) FROM documents;")
    distinct_content = cur.fetchone()[0]

    gap = total - distinct_content
    print(f"  Total rows:              {total}")
    print(f"  Distinct content (md5):  {distinct_content}")
    print(f"  Exact duplicates:        {gap}")

    # Also check metadata content_hash coverage
    cur.execute("SELECT count(*) FROM documents WHERE metadata->>'content_hash' IS NOT NULL;")
    hash_populated = cur.fetchone()[0]
    print(f"  Rows with content_hash in metadata: {hash_populated} / {total}")

    # ── 2. Actual table columns ────────────────────────────────────────────
    print("\n" + "-" * 80)
    print("[2] Actual table columns")
    print("-" * 80)

    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'documents'
        ORDER BY ordinal_position;
    """)
    cols = cur.fetchall()
    print(f"  {'Column':<20} {'Type':<25} {'Nullable'}")
    print(f"  {'-' * 20} {'-' * 25} {'-' * 8}")
    for col_name, data_type, nullable in cols:
        print(f"  {col_name:<20} {data_type:<25} {nullable}")

    # ── 3. ID range and distribution ───────────────────────────────────────
    print("\n" + "-" * 80)
    print("[3] Row ID range and ingestion batches (by ID buckets of 200)")
    print("-" * 80)

    cur.execute("SELECT MIN(id), MAX(id) FROM documents;")
    min_id, max_id = cur.fetchone()
    print(f"  Min ID: {min_id}    Max ID: {max_id}")

    cur.execute("""
        SELECT (id / 200) * 200 AS bucket_start,
               ((id / 200) * 200) + 199 AS bucket_end,
               count(*) AS cnt,
               MIN(id) AS actual_min,
               MAX(id) AS actual_max
        FROM documents
        GROUP BY (id / 200)
        ORDER BY bucket_start;
    """)
    buckets = cur.fetchall()
    print(f"\n  {'ID Range':<20} {'Count':>6}  {'Actual Min-Max'}")
    print(f"  {'-' * 20} {'-' * 6}  {'-' * 20}")
    for bucket_start, bucket_end, cnt, actual_min, actual_max in buckets:
        print(f"  {bucket_start:>6} - {bucket_end:<6}    {cnt:>6}  (ids {actual_min}-{actual_max})")

    # ── 4. Source metadata distribution ────────────────────────────────────
    print("\n" + "-" * 80)
    print("[4] Source metadata distribution")
    print("-" * 80)

    cur.execute("""
        SELECT metadata->>'source' AS source, count(*) AS cnt
        FROM documents
        GROUP BY metadata->>'source'
        ORDER BY cnt DESC;
    """)
    sources = cur.fetchall()
    for source, cnt in sources:
        print(f"  {source or '(null)' :<50} {cnt:>6}")

    # ── 5. Side-by-side comparison of row 782 vs 1303 ──────────────────────
    print("\n" + "-" * 80)
    print("[5] Side-by-side: row 782 vs 1303  (golden query #5)")
    print("    'How do you measure request time when calling the OpenAI API client?'")
    print("-" * 80)

    cur.execute("""
        SELECT id, content, length(content), metadata
        FROM documents
        WHERE id IN (782, 1303)
        ORDER BY id;
    """)
    rows = cur.fetchall()

    contents = []
    for row_id, content, content_len, metadata in rows:
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        source = metadata.get("source", "(none)") if isinstance(metadata, dict) else "(no metadata)"
        contents.append(content)

        print(f"\n  +-- Row id={row_id} " + "-" * 34)
        print(f"  | length(content)  = {content_len}")
        print(f"  | sha256 (first16) = {content_hash}")
        print(f"  | source           = {source}")
        print(f"  | metadata keys    = {list(metadata.keys()) if isinstance(metadata, dict) else metadata}")
        print(f"  |")
        # Print first 600 chars of content, wrapped
        preview = content[:600]
        for line in preview.splitlines():
            wrapped = textwrap.fill(line, width=72, initial_indent="  | ", subsequent_indent="  |   ")
            print(wrapped)
        if len(content) > 600:
            print(f"  | ... [{content_len - 600} more chars truncated]")
        print(f"  +{'-' * 50}")

    if len(contents) == 2:
        if contents[0] == contents[1]:
            print("\n  WARNING: IDENTICAL content -- these are exact duplicates!")
        elif contents[0] in contents[1] or contents[1] in contents[0]:
            print("\n  WARNING: One chunk is a SUBSET of the other (overlapping chunks).")
        else:
            # Check overlap
            shorter = min(contents, key=len)
            longer = max(contents, key=len)
            common = 0
            for i, (a, b) in enumerate(zip(shorter, longer)):
                if a == b:
                    common += 1
            overlap_pct = (common / len(shorter) * 100) if shorter else 0
            print(f"\n  INFO: Different content. Character overlap from start: {common}/{len(shorter)} ({overlap_pct:.1f}%)")

    print("\n" + "=" * 80)
    print("INSPECTION COMPLETE")
    print("=" * 80 + "\n")

    cur.close()
    conn.close()


if __name__ == "__main__":
    inspect()
