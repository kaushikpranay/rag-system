import os
import logging
import psycopg2
import boto3
import json
from dotenv import load_dotenv
from pgvector.psycopg2 import register_vector
load_dotenv()

logger = logging.getLogger(__name__)

RDS_HOST = os.getenv("RDS_HOST")
RDS_PORT = os.getenv("RDS_PORT", 5432)
RDS_DB = os.getenv("RDS_DB", "ragdb")
RDS_USER = os.getenv("RDS_USER", "ragadmin")
RDS_PASSWORD = os.getenv("RDS_PASSWORD")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Reuse a single Bedrock client instead of creating one per-call
_bedrock_client = boto3.client("bedrock-runtime", region_name=AWS_REGION)

def get_connection():
    conn = psycopg2.connect(
        host=RDS_HOST, port=RDS_PORT,
        dbname=RDS_DB, user=RDS_USER,
        password=RDS_PASSWORD
    )
    
    register_vector(conn)
    return conn

def get_bedrock_embedding(text: str) -> list:
    body = json.dumps({"inputText": text})
    response = _bedrock_client.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        contentType="application/json",
        accept="application/json",
        body=body
    )
    result = json.loads(response["body"].read())
    return result["embedding"]

def store_chunks(chunks: list):
    conn = get_connection()
    cur = conn.cursor()
    stored = 0
    for chunk in chunks:
        clean_text = chunk.page_content.replace('\x00', '').strip()
        if not clean_text:
            continue  # skip empty chunks
        embedding = get_bedrock_embedding(clean_text)
        cur.execute(
            "INSERT INTO documents (content, metadata, embedding) VALUES (%s, %s, %s)",
            (clean_text, json.dumps(chunk.metadata), embedding)
        )
        stored += 1
    conn.commit()
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