import pytest
from unittest.mock import MagicMock, patch
from app.memory.dynamodb_client import save_session, MAX_HISTORY_TURNS

def test_save_session_trims_history(capsys):
    fake_history = [{"query": f"q{i}", "answer": f"a{i}"} for i in range(25)]
    with patch("app.memory.dynamodb_client.get_session", return_value=fake_history), \
         patch("app.memory.dynamodb_client.table") as mock_table:
        save_session("session_123", "new_q", "new_a")
        
        captured = capsys.readouterr()
        assert "Trimming session session_123 history" in captured.out
        
        mock_table.put_item.assert_called_once()
        saved_item = mock_table.put_item.call_args[1]["Item"]
        assert len(saved_item["history"]) == MAX_HISTORY_TURNS
        assert saved_item["history"][-1]["query"] == "new_q"

def test_save_session_no_trim_when_under_cap(capsys):
    fake_history = [{"query": f"q{i}", "answer": f"a{i}"} for i in range(5)]
    with patch("app.memory.dynamodb_client.get_session", return_value=fake_history), \
         patch("app.memory.dynamodb_client.table") as mock_table:
        save_session("session_123", "new_q", "new_a")
        
        captured = capsys.readouterr()
        assert "Trimming" not in captured.out
        
        mock_table.put_item.assert_called_once()
        saved_item = mock_table.put_item.call_args[1]["Item"]
        assert len(saved_item["history"]) == 6
