import boto3
from app.escalation.sqs_worker import send_to_sqs
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi import Request
from fastapi.responses import HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional
import uuid
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agent.graph import run_agent
from app.retrieval.pgvector_client import get_connection
from app.escalation.sqs_worker import send_to_sqs
app = FastAPI(title="RAG Query Resolution System")

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        # response.headers["Content-Security-Policy"] = "s|\"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'\"\"default-src 'self'\"|\"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'\"|g"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

app.add_middleware(SecurityHeadersMiddleware)

class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None

class QueryResponse(BaseModel):
    session_id: str
    query: str
    answer: str
    confidence: str
    escalated: bool

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/query", response_model=QueryResponse)
def resolve_query(request: QueryRequest):
    try:
        session_id = request.session_id or str(uuid.uuid4())
        result = run_agent(request.query, session_id)
        return QueryResponse(
            session_id=session_id,
            query=request.query,
            answer=result["answer"],
            confidence=result["confidence"],
            escalated=result["escalate"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/escalate")
async def manual_escalate(request: QueryRequest):
    send_to_sqs(request.session_id, request.query, "Manual escalation requested")
    return {"escalated": True, "session_id": request.session_id}

@app.get("/queue-status/{session_id}")
async def queue_status(session_id: str):
    # Check RDS for human-verified answer
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT content FROM documents WHERE metadata->>'session_id' = %s AND metadata->>'source' = 'human_verified' ORDER BY id DESC LIMIT 1",
        (session_id,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row:
        return {"in_queue": False, "answer": row[0]}
    return {"in_queue": True, "answer": None}

# --- Serve chat UI ---


@app.get("/", response_class=HTMLResponse)
async def chat_ui():
    with open("app/dashboard/chat.html", "r") as f:
        return f.read()