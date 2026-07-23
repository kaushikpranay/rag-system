"""
Tests for the dashboard API (app/api/dashboard.py) that replaced the
Streamlit dashboard's direct AWS access. Boto3's SSM client is stubbed at
import time so this runs in CI without real AWS credentials.
"""
import os
import boto3

os.environ.setdefault("SQS_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/000000000000/fake")
os.environ.setdefault("S3_BUCKET_NAME", "fake-bucket")
os.environ.setdefault("DYNAMODB_TABLE", "fake-table")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")

FAKE_PASSWORD_HASH = "fake-/rag-system/DASHBOARD_PASSWORD_HASH"
os.environ["DASHBOARD_PASSWORD_HASH"] = FAKE_PASSWORD_HASH
_real_client = boto3.client


def _fake_client(service, *args, **kwargs):
    if service == "ssm":
        class FakeSSM:
            def get_parameter(self, Name, WithDecryption=True):
                return {"Parameter": {"Value": f"fake-{Name}"}}
        return FakeSSM()
    return _real_client(service, *args, **kwargs)


boto3.client = _fake_client

from fastapi.testclient import TestClient
from app.api.main import app
from app.api import dashboard as dashboard_module

client = TestClient(app)
AUTH_HEADER = {"Authorization": f"Bearer {FAKE_PASSWORD_HASH}"}
VALID_SESSION_ID = "11111111-1111-1111-1111-111111111111"


def test_login_rejects_wrong_password():
    r = client.post("/dashboard/login", json={"password_hash": "wrong"})
    assert r.status_code == 401


def test_login_accepts_correct_password():
    r = client.post("/dashboard/login", json={"password_hash": FAKE_PASSWORD_HASH})
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_dashboard_routes_reject_missing_auth():
    assert client.get("/dashboard/queue-depth").status_code == 401
    assert client.get("/dashboard/escalations").status_code == 401
    body = {"receipt_handle": "x", "session_id": VALID_SESSION_ID, "query": "q", "answer": "a"}
    assert client.post("/dashboard/escalations/resolve", json=body).status_code == 401


def test_resolve_invokes_all_four_writes(monkeypatch):
    calls = []
    monkeypatch.setattr(dashboard_module, "store_verified_answer", lambda q, a, s: calls.append("rds") or True)
    monkeypatch.setattr(dashboard_module, "archive_verified_answer", lambda s, q, a: calls.append("s3") or True)
    monkeypatch.setattr(dashboard_module, "save_session", lambda s, q, a: calls.append("dynamodb"))
    monkeypatch.setattr(dashboard_module, "delete_from_sqs", lambda r: calls.append("sqs") or True)

    body = {
        "receipt_handle": "abc123",
        "session_id": VALID_SESSION_ID,
        "query": "how do I reset my password?",
        "answer": "Go to settings > security > reset password.",
    }
    r = client.post("/dashboard/escalations/resolve", json=body, headers=AUTH_HEADER)

    assert r.status_code == 200
    assert r.json() == {"resolved": True, "rds_ok": True, "s3_ok": True, "sqs_ok": True}
    assert calls == ["rds", "s3", "dynamodb", "sqs"]


def test_resolve_rejects_invalid_session_id():
    body = {"receipt_handle": "abc123", "session_id": "not-a-uuid", "query": "q", "answer": "a"}
    r = client.post("/dashboard/escalations/resolve", json=body, headers=AUTH_HEADER)
    assert r.status_code == 422


def test_resolve_rejects_empty_answer():
    body = {"receipt_handle": "abc123", "session_id": VALID_SESSION_ID, "query": "q", "answer": "   "}
    r = client.post("/dashboard/escalations/resolve", json=body, headers=AUTH_HEADER)
    assert r.status_code == 422
