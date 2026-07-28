import os
import logging
import time
import hashlib
import socket
import json
import boto3
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import execute_values
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

from app.utils.config import RDS_HOST, RDS_PORT, RDS_DB, RDS_USER, RDS_PASSWORD, AWS_REGION

logger = logging.getLogger(__name__)

DB_POOL_MIN_CONN = int(os.getenv("DB_POOL_MIN_CONN", "2"))
DB_POOL_MAX_CONN = int(os.getenv("DB_POOL_MAX_CONN", "20"))

_pool = None
_db_initialized = False

# Reuse a single Bedrock client instead of creating one per-call
_bedrock_client = boto3.client("bedrock-runtime", region_name=AWS_REGION)


def _get_pool():
    global _pool
    if _pool is None or getattr(_pool, "closed", False):
        try:
            _pool = ThreadedConnectionPool(
                minconn=DB_POOL_MIN_CONN,
                maxconn=DB_POOL_MAX_CONN,
                host=RDS_HOST,
                port=RDS_PORT,
                dbname=RDS_DB,
                user=RDS_USER,
                password=RDS_PASSWORD
            )
        except Exception as e:
            logger.error(f"[pgvector] Failed to initialize connection pool: {e}")
            raise RuntimeError(f"Database connection pool initialization failed: {e}") from e
    return _pool


class PooledConnectionProxy:
    """
    Thin wrapper over a psycopg2 connection returned from ThreadedConnectionPool.
    Delegates all calls to the underlying connection, but calling .close()
    returns the connection back to the pool via pool.putconn(conn).
    """
    def __init__(self, conn, pool):
        self._conn = conn
        self._pool = pool
        self._closed = False

    def close(self):
        if not self._closed:
            self._closed = True
            if self._pool is not None and not getattr(self._pool, "closed", False):
                try:
                    self._pool.putconn(self._conn)
                except Exception as e:
                    logger.warning(f"[pgvector] Failed to return connection to pool: {e}")

    @property
    def closed(self):
        if self._closed:
            return 1
        return self._conn.closed

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __enter__(self):
        self._conn.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self._conn.__exit__(exc_type, exc_val, exc_tb)


def init_db():
    global _db_initialized
    if _db_initialized:
        return
    try:
        pool = _get_pool()
        try:
            conn = pool.getconn()
        except Exception as e:
            logger.error(f"[pgvector] Failed to acquire connection for init_db: {e}")
            raise RuntimeError(f"Database initialization failed: {e}") from e

        try:
            conn.autocommit = True
            cur = conn.cursor()
            try:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS documents (
                        id BIGSERIAL PRIMARY KEY,
                        content TEXT NOT NULL,
                        metadata JSONB DEFAULT '{}',
                        embedding VECTOR(1024),
                        created_at TIMESTAMPTZ DEFAULT now()
                    );
                """)
                cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_content_hash ON documents ((metadata->>'content_hash'));")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_documents_source ON documents ((metadata->>'source'));")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_documents_session_id ON documents ((metadata->>'session_id'));")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_documents_embedding_hnsw ON documents USING hnsw (embedding vector_cosine_ops);")
            finally:
                cur.close()
        finally:
            pool.putconn(conn)

        _db_initialized = True
        logger.info("[pgvector] Database schema initialized successfully (vector extension & documents table).")
    except Exception as e:
        logger.error(f"[pgvector] Database initialization failed: {e}")
        raise


def get_connection():
    if not _db_initialized:
        init_db()
    pool = _get_pool()
    try:
        conn = pool.getconn()
    except Exception as e:
        logger.error(f"[pgvector] Failed to acquire connection from pool: {e}")
        raise RuntimeError(f"Database connection pool exhausted or failed: {e}") from e

    if conn is None:
        raise RuntimeError("Database connection pool returned None")

    conn.autocommit = True
    register_vector(conn)
    return PooledConnectionProxy(conn, pool)


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


def store_chunks(chunks: list) -> int:
    tuples_to_insert = []
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

        tuples_to_insert.append((clean_text, json.dumps(metadata), embedding))

    if not tuples_to_insert:
        logger.info("[pgvector] 0 chunks stored.")
        return 0

    conn = get_connection()
    try:
        cur = conn.cursor()
        try:
            query = """
                INSERT INTO documents (content, metadata, embedding)
                VALUES %s
                ON CONFLICT ((metadata->>'content_hash')) DO NOTHING
                RETURNING id
            """
            inserted_rows = execute_values(cur, query, tuples_to_insert, fetch=True)
            stored = len(inserted_rows) if inserted_rows else 0
        finally:
            cur.close()
    finally:
        conn.close()

    logger.info(f"[pgvector] {stored} chunks stored")
    return stored


def retrieve_similar(query: str, top_k: int = 5, min_similarity: float = 0.3) -> list:
    embedding = get_bedrock_embedding(query)
    if not embedding:
        return []
    embedding_str = "[" + ",".join(map(str, embedding)) + "]"
    conn = get_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT content, metadata, similarity
                FROM (
                    SELECT content, metadata, 1 - (embedding <=> %s::vector) AS similarity
                    FROM documents
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                ) sub
                WHERE similarity >= %s
                """,
                (embedding_str, embedding_str, top_k, min_similarity)
            )
            results = cur.fetchall()
            return [{"content": r[0], "metadata": r[1], "similarity": r[2]} for r in results]
        finally:
            cur.close()
    finally:
        conn.close()


def store_verified_answer(query: str, answer: str, session_id: str = "") -> bool:
    """Store a human-verified Q&A as a new embedding, same shape used by search_human_verified/queue-status."""
    from datetime import datetime, timezone
    text_to_store = f"Q: {query}\nA: {answer}"
    conn = None
    try:
        embedding = get_bedrock_embedding(query)  # embed only the query, matching retrieval
        if not embedding:
            return False
        conn = get_connection()
        cur = conn.cursor()
        try:
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
            return True
        finally:
            cur.close()
    except Exception as e:
        logger.error(f"[pgvector] store_verified_answer error: {e}")
        return False
    finally:
        if conn:
            conn.close()


def search_human_verified(query: str, top_k: int = 3):
    embedding = get_bedrock_embedding(query)
    if not embedding:
        return []
    embedding_str = "[" + ",".join(map(str, embedding)) + "]"
    conn = get_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT content, metadata, 1 - (embedding <=> %s::vector) AS similarity
                FROM documents
                WHERE metadata->>'source' = 'human_verified'
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """, (embedding_str, embedding_str, top_k))
            rows = cur.fetchall()
            return rows
        finally:
            cur.close()
    finally:
        conn.close()