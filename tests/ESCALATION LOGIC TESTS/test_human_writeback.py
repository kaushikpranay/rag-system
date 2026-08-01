"""
Escalation Logic Tests — Human Writeback Resolution
File: tests/ESCALATION LOGIC TESTS/test_human_writeback.py
"""
import pytest
from unittest.mock import patch
from starlette.requests import Request
from app.api.dashboard import resolve_escalation, ResolveRequest


def _make_dummy_request():
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/escalations/resolve",
        "headers": [],
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


@patch("app.api.dashboard.clear_pending")
@patch("app.api.dashboard.delete_from_sqs")
@patch("app.api.dashboard.save_session")
@patch("app.api.dashboard.archive_verified_answer")
@patch("app.api.dashboard.store_verified_answer")
def test_resolve_escalation_success(
    mock_store_verified,
    mock_archive_verified,
    mock_save_session,
    mock_delete_sqs,
    mock_clear_pending,
):
    """
    Test: when store_verified_answer, archive_verified_answer, save_session,
    delete_from_sqs, clear_pending all succeed, response 'resolved' is True
    and all 4 primary mocks are called with correct args (session_id, query, answer).
    """
    mock_store_verified.return_value = True
    mock_archive_verified.return_value = True
    mock_save_session.return_value = None
    mock_delete_sqs.return_value = True
    mock_clear_pending.return_value = True

    session_id = "12345678-1234-5678-1234-567812345678"
    query = "What is the warranty policy?"
    answer = "Our standard warranty is 1 year from purchase."
    receipt_handle = "receipt-handle-abc-123"

    body = ResolveRequest(
        receipt_handle=receipt_handle,
        session_id=session_id,
        query=query,
        answer=answer,
    )

    request = _make_dummy_request()
    response = resolve_escalation(request, body)

    assert response["resolved"] is True
    assert response["rds_ok"] is True
    assert response["s3_ok"] is True
    assert response["sqs_ok"] is True
    assert response["pending_cleared"] is True

    mock_store_verified.assert_called_once_with(query, answer, session_id)
    mock_archive_verified.assert_called_once_with(session_id, query, answer)
    mock_save_session.assert_called_once_with(
        session_id, query, f"[VERIFIED BY AGENT] {answer}"
    )
    mock_delete_sqs.assert_called_once_with(receipt_handle)
    mock_clear_pending.assert_called_once_with(query)


@patch("app.api.dashboard.clear_pending")
@patch("app.api.dashboard.delete_from_sqs")
@patch("app.api.dashboard.save_session")
@patch("app.api.dashboard.archive_verified_answer")
@patch("app.api.dashboard.store_verified_answer")
def test_resolve_escalation_store_verified_fails(
    mock_store_verified,
    mock_archive_verified,
    mock_save_session,
    mock_delete_sqs,
    mock_clear_pending,
):
    """
    Test: when store_verified_answer fails (returns False), response 'resolved' is False.
    """
    mock_store_verified.return_value = False
    mock_archive_verified.return_value = True
    mock_save_session.return_value = None
    mock_delete_sqs.return_value = True
    mock_clear_pending.return_value = True

    session_id = "12345678-1234-5678-1234-567812345678"
    query = "What is the return policy?"
    answer = "30 days return window."
    receipt_handle = "receipt-handle-xyz"

    body = ResolveRequest(
        receipt_handle=receipt_handle,
        session_id=session_id,
        query=query,
        answer=answer,
    )

    request = _make_dummy_request()
    response = resolve_escalation(request, body)

    assert response["resolved"] is False
    assert response["rds_ok"] is False
