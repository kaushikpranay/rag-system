import json
import logging
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, field_validator

from app.api.rate_limit import limiter
from app.escalation.sqs_worker import receive_from_sqs, delete_from_sqs, get_queue_depth
from app.retrieval.pgvector_client import store_verified_answer
from app.archive.s3_client import archive_verified_answer
from app.memory.dynamodb_client import save_session
from app.utils import config

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])


def verify_dashboard_auth(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing credentials")
    token = authorization.removeprefix("Bearer ")
    if token != config.DASHBOARD_PASSWORD_HASH:
        raise HTTPException(status_code=401, detail="Invalid credentials")


class LoginRequest(BaseModel):
    password_hash: str


class ResolveRequest(BaseModel):
    receipt_handle: str
    session_id: str
    query: str
    answer: str

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v):
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError("Invalid session ID format")
        return v

    @field_validator("answer")
    @classmethod
    def validate_answer(cls, v):
        if not v.strip():
            raise ValueError("Answer cannot be empty")
        return v.strip()


@router.post("/login")
def login(body: LoginRequest):
    if body.password_hash != config.DASHBOARD_PASSWORD_HASH:
        raise HTTPException(status_code=401, detail="Incorrect password")
    return {"ok": True}


@router.get("/queue-depth", dependencies=[Depends(verify_dashboard_auth)])
def queue_depth():
    return {"depth": get_queue_depth()}


@router.get("/escalations", dependencies=[Depends(verify_dashboard_auth)])
@limiter.limit("30/minute")
def list_escalations(request: Request, max_messages: int = 5):
    messages = receive_from_sqs(max_messages=max_messages)
    escalations = []
    for msg in messages:
        try:
            body = json.loads(msg.get("Body", "{}"))
        except Exception:
            body = {}
        escalations.append({
            "message_id": msg.get("MessageId", ""),
            "receipt_handle": msg.get("ReceiptHandle", ""),
            "session_id": body.get("session_id", "unknown"),
            "query": body.get("query", ""),
            "answer": body.get("answer", ""),
        })
    return escalations


@router.post("/escalations/resolve", dependencies=[Depends(verify_dashboard_auth)])
@limiter.limit("10/minute")
def resolve_escalation(request: Request, body: ResolveRequest):
    rds_ok = store_verified_answer(body.query, body.answer, body.session_id)
    s3_ok = archive_verified_answer(body.session_id, body.query, body.answer)
    save_session(body.session_id, body.query, f"[VERIFIED BY AGENT] {body.answer}")
    sqs_ok = delete_from_sqs(body.receipt_handle)

    return {
        "resolved": rds_ok and s3_ok and sqs_ok,
        "rds_ok": rds_ok,
        "s3_ok": s3_ok,
        "sqs_ok": sqs_ok,
    }
