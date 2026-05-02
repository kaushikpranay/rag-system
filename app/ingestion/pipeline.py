import os
import boto3
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.retrieval.pgvector_client import store_chunks

load_dotenv()

S3_BUCKET = os.getenv("S3_BUCKET_NAME")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50
)

def load_document_from_s3(s3_key: str) -> list:
    s3 = boto3.client("s3", region_name=AWS_REGION)
    local_path = f"/tmp/{os.path.basename(s3_key)}"
    s3.download_file(S3_BUCKET, s3_key, local_path)
    print(f"[Ingestion] Downloaded to {local_path}")
    loader = PyPDFLoader(local_path)
    return loader.load()

def chunk_documents(documents: list) -> list:
    chunks = splitter.split_documents(documents)
    print(f"[Ingestion] {len(chunks)} chunks created")
    return chunks

def ingest(s3_key: str):
    print(f"[Ingestion] Starting: {s3_key}")
    docs = load_document_from_s3(s3_key)
    chunks = chunk_documents(docs)
    store_chunks(chunks)
    print(f"[Ingestion] Done: {s3_key}")

if __name__ == "__main__":
    ingest("raw-documents/test.pdf")