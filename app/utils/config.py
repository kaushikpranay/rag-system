import boto3
import os

def get_secret(name: str) -> str:
    # Allow reading directly from env variables (e.g. RDS_PASSWORD for /rag-system/RDS_PASSWORD)
    env_name = name.split('/')[-1]
    env_val = os.getenv(env_name)
    if env_val:
        return env_val

    try:
        ssm = boto3.client('ssm', region_name=os.getenv("AWS_REGION", "us-east-1"))
        response = ssm.get_parameter(Name=name, WithDecryption=True)
        return response['Parameter']['Value']
    except Exception as e:
        raise RuntimeError(
            f"Failed to retrieve secret '{name}' from environment variable '{env_name}' "
            f"and AWS SSM fallback failed: {str(e)}"
        ) from e


# AWS
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE")
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL")

# RDS
RDS_HOST = os.getenv("RDS_HOST")
RDS_PORT = os.getenv("RDS_PORT", "5432")
RDS_DB = os.getenv("RDS_DB")
RDS_USER = os.getenv("RDS_USER")
RDS_PASSWORD = get_secret("/rag-system/RDS_PASSWORD")

# Groq
GROQ_API_KEY = get_secret("/rag-system/GROQ_API_KEY")

# Dashboard
DASHBOARD_PASSWORD_HASH = get_secret("/rag-system/DASHBOARD_PASSWORD_HASH")