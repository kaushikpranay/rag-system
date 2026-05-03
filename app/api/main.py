from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional
import uuid
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agent.graph import run_agent

app = FastAPI(title="RAG Query Resolution System")

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
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

