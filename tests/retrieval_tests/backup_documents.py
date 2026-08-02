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


def backup_documents():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, "documents_backup.json")

    conn = get_connection()
    cur = conn.cursor()

    print("\nFetching all rows from documents table...")
    cur.execute("SELECT id, content, metadata::text, embedding::text FROM documents ORDER BY id;")
    rows = cur.fetchall()

    documents = []
    for row_id, content, metadata_text, embedding_text in rows:
        # Parse metadata JSON string back to dict
        try:
            metadata = json.loads(metadata_text) if metadata_text else None
        except (json.JSONDecodeError, TypeError):
            metadata = metadata_text

        documents.append({
            "id": row_id,
            "content": content,
            "metadata": metadata,
            "embedding": embedding_text,
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(documents, f, ensure_ascii=False, indent=2)

    file_size = os.path.getsize(output_path)
    size_mb = file_size / (1024 * 1024)

    print(f"\nTotal rows written: {len(documents)}")
    print(f"Output file:        {output_path}")
    print(f"File size:          {file_size:,} bytes ({size_mb:.2f} MB)")
    print("Backup complete.\n")

    cur.close()
    conn.close()


if __name__ == "__main__":
    backup_documents()
