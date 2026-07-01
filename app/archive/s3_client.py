import os
import json
import time
import logging
import boto3
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET = os.getenv("S3_BUCKET_NAME")

s3 = boto3.client("s3", region_name=AWS_REGION)

def archive_verified_answer(session_id: str, query: str, answer: str) -> bool:
    """Archive a verified answer to S3 under verified-answers/."""
    key = f"verified-answers/{session_id}_{int(time.time())}.json"
    payload = {
        "session_id": session_id,
        "query": query,
        "verified_answer": answer,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=json.dumps(payload),
            ContentType="application/json",
        )
        return True
    except Exception as e:
        logger.error(f"[s3] archive_verified_answer error: {e}")
        return False
