import logging
from app.escalation.sqs_worker import send_to_sqs
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi import Request
from fastapi.responses import HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional
from pathlib import Path
import uuid
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agent.graph import run_agent
from app.retrieval.pgvector_client import get_connection

logger = logging.getLogger(__name__)
app = FastAPI(title="RAG Query Resolution System")

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
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
        logger.error(f"Query resolution failed: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred. Please try again.")

@app.post("/escalate")
async def manual_escalate(request: QueryRequest):
    send_to_sqs(request.session_id, request.query, "Manual escalation requested")
    return {"escalated": True, "session_id": request.session_id}

@app.get("/queue-status/{session_id}")
async def queue_status(session_id: str, query: str = ""):
    """
    Check if a human-verified answer exists for a specific query.
    1. First checks this session's answers matching the exact query.
    2. Falls back to ANY session's answer matching the query (cross-user sharing).
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        row = None

        if query.strip():
            # Priority 1: Match this session + this exact query
            cur.execute(
                "SELECT content FROM documents WHERE metadata->>'source' = 'human_verified' AND metadata->>'session_id' = %s AND LOWER(metadata->>'query') = LOWER(%s) ORDER BY id DESC LIMIT 1",
                (session_id, query.strip())
            )
            row = cur.fetchone()

            if not row:
                # Priority 2: Match ANY session with same query (cross-user sharing)
                cur.execute(
                    "SELECT content FROM documents WHERE metadata->>'source' = 'human_verified' AND LOWER(metadata->>'query') = LOWER(%s) ORDER BY id DESC LIMIT 1",
                    (query.strip(),)
                )
                row = cur.fetchone()
        else:
            # Legacy fallback (no query provided)
            cur.execute(
                "SELECT content FROM documents WHERE metadata->>'session_id' = %s AND metadata->>'source' = 'human_verified' ORDER BY id DESC LIMIT 1",
                (session_id,)
            )
            row = cur.fetchone()

        cur.close()
    finally:
        conn.close()

    if row:
        return {"in_queue": False, "answer": row[0]}
    return {"in_queue": True, "answer": None}

CHAT_HTML_PATH = Path(__file__).parent.parent / "dashboard" / "chat.html"

@app.get("/", response_class=HTMLResponse)
async def chat_ui():
    with open(CHAT_HTML_PATH, "r") as f:
        return f.read()