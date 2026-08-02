"""
Conversation-Session Tests — Follow-up Turn Recording
File: tests/CONVERSATION-SESSION TESTS/test_followup.py
"""
import pytest
from unittest.mock import patch
from app.memory.dynamodb_client import save_session, get_session


@patch("app.memory.dynamodb_client.table")
def test_save_and_get_two_turns_followup(mock_table):
    """
    Test: save two turns via save_session for the same session_id,
    then get_session returns both in order with correct query/answer fields.
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

    session_id = "test-session-followup"

    # Turn 1
    save_session(session_id, "What is your return policy?", "30 days return window.")

    # Turn 2 (Follow-up)
    save_session(session_id, "Does it apply to international orders?", "Yes, international returns are accepted.")

    history = get_session(session_id)

    assert len(history) == 2
    assert history[0]["query"] == "What is your return policy?"
    assert history[0]["answer"] == "30 days return window."
    assert history[1]["query"] == "Does it apply to international orders?"
    assert history[1]["answer"] == "Yes, international returns are accepted."
