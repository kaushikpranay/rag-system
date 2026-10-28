import boto3
import os
import json
import hashlib
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL")
DYNAMODB_PENDING_TABLE = os.getenv("DYNAMODB_PENDING_TABLE", "rag-pending-escalations")

_sqs = None
_pending_table = None

def _get_sqs():
    global _sqs
    if _sqs is None:
        _sqs = boto3.client("sqs", region_name=os.getenv("AWS_REGION", "ap-southeast-2"))
    return _sqs

def _get_pending_table():
    global _pending_table
    if _pending_table is None:
        dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "ap-southeast-2"))
        _pending_table = dynamodb.Table(os.getenv("DYNAMODB_PENDING_TABLE", "rag-pending-escalations"))
    return _pending_table


def is_duplicate_pending(query: str) -> bool:
    try:
        normalized = query.strip().lower()
        query_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        response = _get_pending_table().get_item(Key={"query_hash": query_hash})
        item = response.get("Item")
        if not item:
            return False
        expires_at = item.get("expires_at", 0)
        current_time = int(datetime.now(timezone.utc).timestamp())
        if expires_at > current_time:
            return True
        return False
    except Exception as e:
        print(f"[dynamodb] is_duplicate_pending error: {e}")
        return False


def mark_pending(query: str) -> None:
    try:
        normalized = query.strip().lower()
        query_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        now = datetime.now(timezone.utc)
        created_at = now.isoformat()
        expires_at = int((now + timedelta(hours=1)).timestamp())
        _get_pending_table().put_item(Item={
            "query_hash": query_hash,
            "query": query,
            "created_at": created_at,
            "expires_at": expires_at
        })
    except Exception as e:
        print(f"[dynamodb] mark_pending error: {e}")


def clear_pending(query: str) -> bool:
    try:
        normalized = query.strip().lower()
        query_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        _get_pending_table().delete_item(Key={"query_hash": query_hash})
        print(f"[dynamodb] Pending escalation cleared for query: {query}")
        return True
    except Exception as e:
        print(f"[dynamodb] clear_pending error: {e}")
        return False


def send_to_sqs(session_id: str, query: str, answer: str) -> bool:
    try:
        if is_duplicate_pending(query):
            print(f"[sqs] Query is already pending, skipping SQS send: {query}")
            return True

        mark_pending(query)

        message = {
            "session_id": session_id,
            "query": query, 
            "answer": answer
        }

        _get_sqs().send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps(message)
        )

        print(f"[sqs] Escalated query sent: {query}")
        return True
    except Exception as e:
        print(f"[sqs] send_to_sqs error: {e}")
        return False


def receive_from_sqs(max_messages: int = 10) -> list:
    try:
        response = _get_sqs().receive_message(
            QueueUrl=SQS_QUEUE_URL,
            MaxNumberOfMessages=max_messages,
            WaitTimeSeconds=5
        )
        return response.get("Messages", [])
    except Exception as e:
        print(f"[sqs] receive_from_sqs error: {e}")
        return []


def delete_from_sqs(receipt_handle: str) -> bool:
    try:
        _get_sqs().delete_message(
            QueueUrl=SQS_QUEUE_URL,
            ReceiptHandle=receipt_handle
        )
        print(f"[sqs] Message deleted")
        return True
    except Exception as e:
        print(f"[sqs] delete_from_sqs error: {e}")
        return False


def get_queue_depth() -> int:
    try:
        resp = _get_sqs().get_queue_attributes(
            QueueUrl=SQS_QUEUE_URL,
            AttributeNames=["ApproximateNumberOfMessages"]
        )
        return int(resp["Attributes"].get("ApproximateNumberOfMessages", 0))
    except Exception as e:
        print(f"[sqs] get_queue_depth error: {e}")
        return -1