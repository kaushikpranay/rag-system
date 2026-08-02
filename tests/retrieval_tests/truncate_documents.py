import os
import sys
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


def truncate_documents():
    conn = get_connection()
    cur = conn.cursor()

    # 1. Row count before truncation
    cur.execute("SELECT count(*) FROM documents;")
    count_before = cur.fetchone()[0]
    print(f"Row count before truncation: {count_before}")

    # 2. Run TRUNCATE TABLE documents RESTART IDENTITY;
    print("Truncating 'documents' table and restarting identity sequence...")
    cur.execute("TRUNCATE TABLE documents RESTART IDENTITY;")
    conn.commit()

    # 3. Row count after truncation
    cur.execute("SELECT count(*) FROM documents;")
    count_after = cur.fetchone()[0]
    print(f"Row count after truncation:  {count_after}")

    if count_after == 0:
        print("\nSuccess: 'documents' table successfully truncated to 0 rows.")
    else:
        print(f"\nWarning: Expected 0 rows after truncation, but found {count_after}.")

    cur.close()
    conn.close()


if __name__ == "__main__":
    truncate_documents()
