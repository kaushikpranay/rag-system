import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')
    AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
    S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
    DYNAMODB_TABLE = os.getenv('DYNAMODB_TABLE', 'rag-session-memory')
    SQS_QUEUE_URL = os.getenv('SQS_QUEUE_URL')
    CHROMA_PORT = os.getenv('CHROMA_PORT', 'localhost')
    CHROMA_HOST = os.getenv('CHROMA_HOST', 8000)
    LANGSMITH_API_KEY = os.getenv('LANGSMITH_API_KEY')
    LANGSMITH_PROJECT = os.getenv('LANGSMITH_PROJECT', 'rag-system')


config = Config()
