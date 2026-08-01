"""
Conversation-Session Tests — Session Isolation
File: tests/CONVERSATION-SESSION TESTS/test_session_isolation.py
"""
import pytest
from unittest.mock import patch
from app.memory.dynamodb_client import save_session, get_session


@patch("app.memory.dynamodb_client.table")
def test_session_isolation_a_and_b(mock_table):
    """
    Test: save_session for session_id "A" and session_id "B" separately;
    assert get_session("A") does not contain session B's data and vice versa.
    """
    db_store = {}

    def fake_get_item(Key):
        sid = Key.get("session_id")
        if sid in db_store:
            return {"Item": db_store[sid]}
        return {}

    def fake_put_item(Item):
        sid = Item.get("session_id")
        db_store[sid] = Item

    mock_table.get_item.side_effect = fake_get_item
    mock_table.put_item.side_effect = fake_put_item

    # Save turn in session A
    save_session("session_A", "User A question", "User A answer")

    # Save turn in session B
    save_session("session_B", "User B question", "User B answer")

    history_a = get_session("session_A")
    history_b = get_session("session_B")

    assert len(history_a) == 1
    assert history_a[0]["query"] == "User A question"
    assert history_a[0]["answer"] == "User A answer"

    assert len(history_b) == 1
    assert history_b[0]["query"] == "User B question"
    assert history_b[0]["answer"] == "User B answer"

    # Verify session A does not contain session B data
    queries_a = [turn["query"] for turn in history_a]
    assert "User B question" not in queries_a

    # Verify session B does not contain session A data
    queries_b = [turn["query"] for turn in history_b]
    assert "User A question" not in queries_b
