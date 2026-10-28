import boto3
import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", "rag-session-memory")
AWS_REGION = os.getenv("AWS_REGION", "ap-southeast-2")
MAX_HISTORY_TURNS = 20

table = None

def _get_table():
    global table
    if table is None:
        try:
            dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
            table = dynamodb.Table(DYNAMODB_TABLE)
        except Exception as e:
            print(f"[dynamodb] init table error: {e}")
            return None
    return table

def get_session(session_id: str) -> list:
    t = table or _get_table()
    if t is None:
        return []
    try:
        response = t.get_item(Key={"session_id": session_id})
        item = response.get("Item")
        if not item:
            return []
        return item.get("history", [])
    except Exception as e:
        print(f"[dynamodb] get_session error: {e}")
        return []

def save_session(session_id: str, query: str, answer: str) -> None:
    t = table or _get_table()
    if t is None:
        return
    try:
        history = get_session(session_id)
        history.append({
            "query": query,
            "answer": answer,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        if len(history) > MAX_HISTORY_TURNS:
            print(f"[dynamodb] Trimming session {session_id} history from {len(history)} to {MAX_HISTORY_TURNS} entries")
            history = history[-MAX_HISTORY_TURNS:]
        ttl = int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp())
        t.put_item(Item={
            "session_id": session_id,
            "history": history,
            "expires_at": ttl
        })
    except Exception as e:
        print(f"[dynamodb] save_session error: {e}")