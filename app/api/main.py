import logging
import re
from app.escalation.sqs_worker import send_to_sqs
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, field_validator
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional
import uuid
import sys
import os

# Rate limiting
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from fastapi.middleware.cors import CORSMiddleware

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agent.graph import run_agent
from contextlib import asynccontextmanager
from app.retrieval.pgvector_client import get_connection, init_db
from app.utils.sanitizer import sanitize_query, detect_prompt_injection, mask_pii
from app.api.rate_limit import limiter
from app.api.dashboard import router as dashboard_router

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        logger.info("Database initialized successfully at app startup.")
    except Exception as e:
        logger.error(f"Failed to initialize database at startup: {e}")
    yield

# ─── Rate Limiter Setup ──────────────────────────────────────────────────────
app = FastAPI(title="RAG Query Resolution System", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ─── CORS (React frontends, hosted separately from this API) ────────────────
FRONTEND_ORIGINS = [o.strip() for o in os.getenv("FRONTEND_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# ─── Security Headers Middleware ─────────────────────────────────────────────
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

app.include_router(dashboard_router, prefix="/dashboard")

# ─── Request / Response Models ───────────────────────────────────────────────
class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None

    @field_validator("query")
    @classmethod
    def validate_query(cls, v):
        cleaned = sanitize_query(v)
        if not cleaned:
            raise ValueError("Query cannot be empty")
        if len(cleaned) > 1000:
            raise ValueError("Query exceeds maximum length of 1000 characters")
        return cleaned

class QueryResponse(BaseModel):
    session_id: str
    query: str
    answer: str
    confidence: str
    escalated: bool

# ─── Endpoints ───────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/query", response_model=QueryResponse)
@limiter.limit("20/minute")
def resolve_query(request: Request, body: QueryRequest):
    try:
        session_id = body.session_id or str(uuid.uuid4())

        # Log with PII masked
        logger.info(f"[query] session={session_id} query={mask_pii(body.query[:80])}")

        # Check for prompt injection attempts
        if detect_prompt_injection(body.query):
            logger.warning(f"[query] Prompt injection blocked for session={session_id}")
            return QueryResponse(
                session_id=session_id,
                query=body.query,
                answer="I can only help with customer support questions. Please rephrase your question.",
                confidence="blocked",
                escalated=False
            )

        result = run_agent(body.query, session_id)
        return QueryResponse(
            session_id=session_id,
            query=body.query,
            answer=result["answer"],
            confidence=result["confidence"],
            escalated=result["escalate"]
        )
    except Exception as e:
        logger.error(f"Query resolution failed: {e}")
        raise HTTPException(status_code=500, detail="An internal error occurred. Please try again.")

@app.post("/escalate")
@limiter.limit("5/minute")
def manual_escalate(request: Request, body: QueryRequest):
    session_id = body.session_id or str(uuid.uuid4())

    # Validate session_id format (must be a UUID)
    try:
        uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format")

    send_to_sqs(session_id, body.query, "Manual escalation requested")
    return {"escalated": True, "session_id": session_id}

@app.get("/queue-status/{session_id}")
@limiter.limit("30/minute")
def queue_status(request: Request, session_id: str, query: str = ""):
    """
    Check if a human-verified answer exists for a specific query.
    1. First checks this session's answers matching the exact query.
    2. Falls back to ANY session's answer matching the query (cross-user sharing).
    """
    # Validate session_id format
    try:
        uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format")

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