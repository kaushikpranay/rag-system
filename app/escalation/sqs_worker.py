import boto3
import os
import json
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL")

sqs = boto3.client("sqs", region_name=AWS_REGION)

def send_to_sqs(session_id: str, query: str, answer: str) -> bool:
    try:
        message = {
            "session_id": session_id,
            "query": query, 
            "answer": answer
        }

        sqs.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps(message)
        )

        print(f"[sqs] Escalated query sent: {query}")
        return True
    except Exception as e:
        print(f"[sqs] send_to_sqs error: {e}")
        return False

def receive_from_sqs(max_messages: int=10)-> list:
    try:
        response = sqs.receive_message(
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
        sqs.delete_message(
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
        resp = sqs.get_queue_attributes(
            QueueUrl=SQS_QUEUE_URL,
            AttributeNames=["ApproximateNumberOfMessages"]
        )
        return int(resp["Attributes"].get("ApproximateNumberOfMessages", 0))
    except Exception as e:
        print(f"[sqs] get_queue_depth error: {e}")
        return -1
        

        