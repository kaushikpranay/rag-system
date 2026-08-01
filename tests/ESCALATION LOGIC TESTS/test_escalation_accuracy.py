"""
Escalation Logic Tests — Escalation Accuracy & Deduplication
File: tests/ESCALATION LOGIC TESTS/test_escalation_accuracy.py
"""
import pytest
from unittest.mock import patch, MagicMock
from app.escalation.sqs_worker import send_to_sqs


@patch("app.escalation.sqs_worker.sqs")
@patch("app.escalation.sqs_worker.pending_table")
@patch("app.escalation.sqs_worker.is_duplicate_pending")
def test_send_to_sqs_first_and_second_call(mock_is_dup, mock_pending_table, mock_sqs):
    """
    Test send_to_sqs:
    1. First call with a new query sends to SQS and marks pending (assert sqs.send_message called once).
    2. Second call with the same query (before expiry) does NOT send again (assert send_message call count stays at 1, is_duplicate_pending mocked to return True).
    """
    session_id = "sess-12345"
    query = "How do I request a refund?"
    answer = "I don't have enough information to answer this."

    # First call: query is NOT pending yet
    mock_is_dup.return_value = False
    result_first = send_to_sqs(session_id, query, answer)

    assert result_first is True
    assert mock_sqs.send_message.call_count == 1
    mock_pending_table.put_item.assert_called_once()

    # Second call: query IS pending (is_duplicate_pending returns True)
    mock_is_dup.return_value = True
    result_second = send_to_sqs(session_id, query, answer)

    assert result_second is True
    # send_message must NOT be called again (count remains 1)
    assert mock_sqs.send_message.call_count == 1
