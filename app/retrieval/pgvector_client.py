import os
import logging
import time
import hashlib
import socket
import psycopg2
import boto3
import json
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from pgvector.psycopg2 import register_vector
load_dotenv()

TUNNEL_LOCAL_PORT = int(os.getenv("TUNNEL_LOCAL_PORT", "15432"))

def _check_port(port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        return False

if _check_port(TUNNEL_LOCAL_PORT):
    os.environ["RDS_HOST"] = "127.0.0.1"
    os.environ["RDS_PORT"] = str(TUNNEL_LOCAL_PORT)
elif _check_port(5432):
    os.environ["RDS_HOST"] = "127.0.0.1"
    os.environ["RDS_PORT"] = "5432"

logger = logging.getLogger(__name__)

RDS_HOST = os.getenv("RDS_HOST", "localhost")
RDS_PORT = os.getenv("RDS_PORT", 5432)
RDS_DB = os.getenv("RDS_DB", "ragdb")
RDS_USER = os.getenv("RDS_USER", "ragadmin")
RDS_PASSWORD = os.getenv("RDS_PASSWORD", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Reuse a single Bedrock client instead of creating one per-call
_bedrock_client = boto3.client("bedrock-runtime", region_name=AWS_REGION)

_db_initialized = False

def init_db():
    global _db_initialized
    if _db_initialized:
        return
    try:
        conn = psycopg2.connect(
            host=RDS_HOST, port=RDS_PORT,
            dbname=RDS_DB, user=RDS_USER,
            password=RDS_PASSWORD
        )
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id BIGSERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                metadata JSONB,
                embedding vector(1024),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_documents_metadata_source ON documents ((metadata->>'source'));")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_documents_metadata_session_id ON documents ((metadata->>'session_id'));")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_content_hash_unique ON documents ((metadata->>'content_hash'));")
        cur.close()
        conn.close()
        _db_initialized = True
        logger.info("[pgvector] Database schema initialized successfully (vector extension & documents table).")
    except Exception as e:
        logger.error(f"[pgvector] Database initialization failed: {e}")
        raise

def get_connection():
    if not _db_initialized:
        init_db()
    conn = psycopg2.connect(
        host=RDS_HOST, port=RDS_PORT,
        dbname=RDS_DB, user=RDS_USER,
        password=RDS_PASSWORD
    )
    conn.autocommit = True
    register_vector(conn)
    return conn

def get_bedrock_embedding(text: str) -> list:
    if len(text) == 0:
        logger.warning("[pgvector] Empty text passed to get_bedrock_embedding, skipping Bedrock call.")
        return []

    delays = [1, 2, 4]
    max_retries = len(delays)
    for attempt in range(max_retries + 1):
        try:
            body = json.dumps({"inputText": text})
            response = _bedrock_client.invoke_model(
                modelId="amazon.titan-embed-text-v2:0",
                contentType="application/json",
                accept="application/json",
                body=body
            )
            result = json.loads(response["body"].read())
            return result["embedding"]
        except Exception as e:
            if attempt < max_retries:
                delay = delays[attempt]
                logger.warning(
                    f"[pgvector] Bedrock invoke_model failed with {type(e).__name__} ({e}). "
                    f"Retrying in {delay}s (attempt {attempt + 1}/{max_retries})..."
                )
                time.sleep(delay)
            else:
                logger.error(f"[pgvector] Bedrock invoke_model failed after {max_retries} retries: {e}")
                raise

def store_chunks(chunks: list):
    conn = get_connection()
    cur = conn.cursor()
    stored = 0
    try:
        for chunk in chunks:
            clean_text = chunk.page_content.replace('\x00', '').strip()
            if not clean_text:
                continue

            content_hash = hashlib.sha256(clean_text.encode("utf-8")).hexdigest()
            metadata = dict(chunk.metadata) if chunk.metadata else {}
            metadata["content_hash"] = content_hash

            try:
                embedding = get_bedrock_embedding(clean_text)
            except Exception as e:
                logger.error(f"[pgvector] Embedding failed, skipping chunk: {e}")
                continue

            if not embedding:
                logger.warning(f"[pgvector] Empty embedding returned for chunk, skipping insertion: {clean_text[:50]}...")
                continue

            cur.execute(
                """INSERT INTO documents (content, metadata, embedding)
                   VALUES (%s, %s, %s)
                   ON CONFLICT ((metadata->>'content_hash')) DO NOTHING
                   RETURNING id""",
                (clean_text, json.dumps(metadata), embedding)
            )
            stored += 1 if cur.fetchone() else 0
    finally:
        cur.close()
        conn.close()
    logger.info(f"[pgvector] {stored} chunks stored")

def retrieve_similar(query: str, top_k: int = 5, min_similarity: float = 0.3) -> list:
    embedding = get_bedrock_embedding(query)
    embedding_str = "[" + ",".join(map(str, embedding)) + "]"
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT content, metadata, 1 - (embedding <=> %s::vector) AS similarity
        FROM documents
        WHERE 1 - (embedding <=> %s::vector) > %s
        ORDER BY embedding <=> %s::vector
        LIMIT %s
        """,
        (embedding_str, embedding_str, min_similarity, embedding_str, top_k)
    )
    results = cur.fetchall()
    cur.close()
    conn.close()
    return [{"content": r[0], "metadata": r[1], "similarity": r[2]} for r in results]



def store_verified_answer(query: str, answer: str, session_id: str = "") -> bool:
    """Store a human-verified Q&A as a new embedding, same shape used by search_human_verified/queue-status."""
    from datetime import datetime, timezone
    text_to_store = f"Q: {query}\nA: {answer}"
    embedding = get_bedrock_embedding(query)  # embed only the query, matching retrieval
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO documents (content, metadata, embedding) VALUES (%s, %s, %s)",
            (
                text_to_store,
                json.dumps({
                    "source": "human_verified",
                    "query": query,
                    "session_id": session_id,
                    "verified_at": datetime.now(timezone.utc).isoformat(),
                }),
                embedding,
            ),
        )
        conn.commit()
        cur.close()
        return True
    except Exception as e:
        logger.error(f"[pgvector] store_verified_answer error: {e}")
        return False
    finally:
        if conn:
            conn.close()


def search_human_verified(query: str, top_k: int = 3):
    conn = get_connection()
    cur = conn.cursor()
    embedding = get_bedrock_embedding(query)
    embedding_str = "[" + ",".join(map(str, embedding)) + "]"
    cur.execute("""
        SELECT content, metadata, 1 - (embedding <=> %s::vector) AS similarity
        FROM documents
        WHERE metadata->>'source' = 'human_verified'
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (embedding_str, embedding_str, top_k))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows