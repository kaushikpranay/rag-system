import os
import boto3
import tempfile
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.retrieval.pgvector_client import store_chunks

load_dotenv()

S3_BUCKET = os.getenv("S3_BUCKET_NAME")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=100
)

def load_document_from_s3(s3_key: str) -> list:
    s3 = boto3.client("s3", region_name=AWS_REGION)
    tmp_dir = tempfile.mkdtemp()
    local_path = os.path.join(tmp_dir, os.path.basename(s3_key))
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
    # Ingest all PDFs in raw-documents/ folder from S3
    s3 = boto3.client('s3', region_name=AWS_REGION)
    response = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix="raw-documents/")
    
    if 'Contents' not in response:
        print("[Ingestion] No files found in raw-documents/")
    else:
        for obj in response['Contents']:
            key = obj['Key']
            if key.endswith('.pdf'):
                print(f"[Ingestion] Processing: {key}")
                try:
                    ingest(key)
                except Exception as e:
                    print(f"[Ingestion] FAILED: {key} — {e}")
                    continue