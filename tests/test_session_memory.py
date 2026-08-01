import pytest
from unittest.mock import patch, MagicMock
from app.memory.dynamodb_client import save_session, MAX_HISTORY_TURNS

def test_save_session_history_cap():
    session_id = "test_session_cap"
    storage = {}

    def mock_get_item(Key):
        sid = Key.get("session_id")
        if sid in storage:
            # Return deep enough copy of item so mutation in save_session works cleanly
            item = storage[sid]
            return {"Item": {"session_id": item["session_id"], "history": list(item.get("history", [])), "expires_at": item.get("expires_at")}}
        return {}

    def mock_put_item(Item):
        sid = Item.get("session_id")
        storage[sid] = Item

    mock_table = MagicMock()
    mock_table.get_item.side_effect = mock_get_item
    mock_table.put_item.side_effect = mock_put_item

    with patch("app.memory.dynamodb_client.table", mock_table):
        for i in range(27):
            save_session(session_id, f"Query {i}", f"Answer {i}")

    assert mock_table.put_item.call_count == 27
    final_put_call = mock_table.put_item.call_args
    saved_item = final_put_call.kwargs.get("Item") if final_put_call.kwargs else final_put_call[1].get("Item")
    
    assert saved_item is not None
    assert len(saved_item["history"]) <= MAX_HISTORY_TURNS
    assert len(saved_item["history"]) == 20
    assert saved_item["history"][-1]["query"] == "Query 26"
