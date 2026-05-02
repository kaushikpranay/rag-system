import os
import psycopg2
import boto3
import json
from dotenv import load_dotenv
from pgvector.psycopg2 import register_vector
load_dotenv()

RDS_HOST = os.getenv("RDS_HOST")
RDS_PORT = os.getenv("RDS_PORT", 5432)
RDS_DB = os.getenv("RDS_DB", "ragdb")
RDS_USER = os.getenv("RDS_USER", "ragadmin")
RDS_PASSWORD = os.getenv("RDS_PASSWORD")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

def get_connection():
    conn = psycopg2.connect(
        host=RDS_HOST, port=RDS_PORT,
        dbname=RDS_DB, user=RDS_USER,
        password=RDS_PASSWORD
    )
    
    register_vector(conn)
    return conn

def get_bedrock_embedding(text: str) -> list:
    client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
    body = json.dumps({"inputText": text})
    response = client.invoke_model(
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
    for chunk in chunks:
        embedding = get_bedrock_embedding(chunk.page_content)
        cur.execute(
            "INSERT INTO documents (content, metadata, embedding) VALUES (%s, %s, %s)",
            (chunk.page_content, json.dumps(chunk.metadata), embedding)
        )
    conn.commit()
    cur.close()
    conn.close()
    print(f"[pgvector] {len(chunks)} chunks stored")

def retrieve_similar(query: str, top_k: int = 5) -> list:
    embedding = get_bedrock_embedding(query)
    embedding_str = "[" + ",".join(map(str, embedding)) + "]"
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT content, metadata, 1 - (embedding <=> %s::vector) AS similarity
        FROM documents
        ORDER BY embedding <=> %s::vector
        LIMIT %s
        """,
        (embedding_str, embedding_str, top_k)
    )
    results = cur.fetchall()
    cur.close()
    conn.close()
    return [{"content": r[0], "metadata": r[1], "similarity": r[2]} for r in results]