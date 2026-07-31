import pytest
from unittest.mock import MagicMock, patch
from app.agent.graph import AgentState, context_node, llm_node


def test_agent_state_schema():
    assert "truncated" in AgentState.__annotations__
    assert AgentState.__annotations__["truncated"] is bool


def test_context_node_under_budget():
    state: AgentState = {
        "query": "test query",
        "session_id": "s1",
        "chat_history": [],
        "retrieved_chunks": [
            {"content": "short chunk 1", "similarity": 0.9},
            {"content": "short chunk 2", "similarity": 0.8},
        ],
        "context": "",
        "answer": "",
        "confidence": "",
        "escalate": False,
        "retry_count": 0,
        "error": None,
        "truncated": False,
    }

    res = context_node(state)
    assert len(res["retrieved_chunks"]) == 2
    assert "short chunk 1" in res["context"]
    assert "short chunk 2" in res["context"]


def test_context_node_exceeds_budget_truncates_lowest_similarity():
    # Build 3 large chunks; lowest similarity = 0.5
    large_text_high = "A" * 10000   # ~2500 tokens, sim 0.95
    large_text_med = "B" * 10000    # ~2500 tokens, sim 0.75
    large_text_low = "C" * 10000    # ~2500 tokens, sim 0.50

    chunks = [
        {"content": large_text_low, "similarity": 0.50},
        {"content": large_text_high, "similarity": 0.95},
        {"content": large_text_med, "similarity": 0.75},
    ]

    state: AgentState = {
        "query": "test query",
        "session_id": "s1",
        "chat_history": [],
        "retrieved_chunks": chunks,
        "context": "",
        "answer": "",
        "confidence": "",
        "escalate": False,
        "retry_count": 0,
        "error": None,
        "truncated": False,
    }

    res = context_node(state)
    # Total characters originally ~30,000 => ~7500 tokens > 6000
    # Dropping lowest similarity chunk (sim 0.50) leaves 2 chunks (~20,000 chars => ~5000 tokens <= 6000)
    assert len(res["retrieved_chunks"]) == 2
    remaining_sims = [c["similarity"] for c in res["retrieved_chunks"]]
    assert 0.50 not in remaining_sims
    assert 0.95 in remaining_sims
    assert 0.75 in remaining_sims
    assert len(res["context"]) // 4 <= 6000


@patch("app.agent.graph.Groq")
def test_llm_node_finish_reason_length(mock_groq):
    mock_client = MagicMock()
    mock_groq.return_value = mock_client
    
    mock_choice = MagicMock()
    mock_choice.message.content = "Truncated text..."
    mock_choice.finish_reason = "length"
    
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    state: AgentState = {
        "query": "test query",
        "session_id": "s1",
        "chat_history": [],
        "retrieved_chunks": [],
        "context": "some context",
        "answer": "",
        "confidence": "",
        "escalate": False,
        "retry_count": 0,
        "error": None,
        "truncated": False,
    }

    res = llm_node(state)
    assert res["answer"] == "Truncated text..."
    assert res["truncated"] is True


@patch("app.agent.graph.Groq")
def test_llm_node_finish_reason_stop(mock_groq):
    mock_client = MagicMock()
    mock_groq.return_value = mock_client
    
    mock_choice = MagicMock()
    mock_choice.message.content = "Complete answer."
    mock_choice.finish_reason = "stop"
    
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    state: AgentState = {
        "query": "test query",
        "session_id": "s1",
        "chat_history": [],
        "retrieved_chunks": [],
        "context": "some context",
        "answer": "",
        "confidence": "",
        "escalate": False,
        "retry_count": 0,
        "error": None,
        "truncated": False,
    }

    res = llm_node(state)
    assert res["answer"] == "Complete answer."
    assert res["truncated"] is False


@patch("time.sleep")
@patch("app.agent.graph.Groq")
def test_llm_node_retry_logic_recovers(mock_groq, mock_sleep):
    mock_client = MagicMock()
    mock_groq.return_value = mock_client

    mock_choice = MagicMock()
    mock_choice.message.content = "Recovered answer."
    mock_choice.finish_reason = "stop"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    # Fail on first attempt, succeed on second attempt
    mock_client.chat.completions.create.side_effect = [RuntimeError("API transient error"), mock_response]

    state: AgentState = {
        "query": "test query",
        "session_id": "s1",
        "chat_history": [],
        "retrieved_chunks": [],
        "context": "some context",
        "answer": "",
        "confidence": "",
        "escalate": False,
        "retry_count": 0,
        "error": None,
        "truncated": False,
    }

    res = llm_node(state)
    assert res["answer"] == "Recovered answer."
    assert res["truncated"] is False
    assert mock_client.chat.completions.create.call_count == 2
    mock_sleep.assert_called_once_with(1)


@patch("time.sleep")
@patch("app.agent.graph.Groq")
def test_llm_node_retry_logic_fails_after_all_retries(mock_groq, mock_sleep):
    mock_client = MagicMock()
    mock_groq.return_value = mock_client

    # Fail on all 3 attempts (initial + 2 retries)
    mock_client.chat.completions.create.side_effect = RuntimeError("Persistent API error")

    state: AgentState = {
        "query": "test query",
        "session_id": "s1",
        "chat_history": [],
        "retrieved_chunks": [],
        "context": "some context",
        "answer": "",
        "confidence": "",
        "escalate": False,
        "retry_count": 0,
        "error": None,
        "truncated": False,
    }

    res = llm_node(state)
    assert "technical difficulties" in res["answer"]
    assert res["truncated"] is False
    assert mock_client.chat.completions.create.call_count == 3
    assert mock_sleep.call_args_list == [((1,),), ((2,),)]


@patch("app.agent.graph.Groq")
def test_check_groundedness_yes(mock_groq):
    from app.agent.graph import check_groundedness
    mock_client = MagicMock()
    mock_groq.return_value = mock_client
    mock_choice = MagicMock()
    mock_choice.message.content = "YES"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    assert check_groundedness("The item costs $10.", "The item costs $10.") is True


@patch("app.agent.graph.Groq")
def test_check_groundedness_no(mock_groq):
    from app.agent.graph import check_groundedness
    mock_client = MagicMock()
    mock_groq.return_value = mock_client
    mock_choice = MagicMock()
    mock_choice.message.content = "NO"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    assert check_groundedness("The item costs $100.", "The item costs $10.") is False


@patch("app.agent.graph.Groq")
def test_check_groundedness_exception_fail_open(mock_groq):
    from app.agent.graph import check_groundedness
    mock_client = MagicMock()
    mock_groq.return_value = mock_client
    mock_client.chat.completions.create.side_effect = Exception("API error")

    assert check_groundedness("The item costs $10.", "The item costs $10.") is True


@patch("app.agent.graph.check_groundedness")
def test_evaluation_node_un_grounded_retries(mock_grounded):
    from app.agent.graph import evaluation_node
    mock_grounded.return_value = False

    state: AgentState = {
        "query": "test query",
        "session_id": "s1",
        "chat_history": [],
        "retrieved_chunks": [{"content": "c1"}],
        "context": "c1",
        "answer": "Hallucinated answer",
        "confidence": "",
        "escalate": False,
        "retry_count": 0,
        "error": None,
        "truncated": False,
    }

    res = evaluation_node(state)
    assert res["confidence"] == "retry"
    assert res["retry_count"] == 1
    assert res["escalate"] is False


@patch("app.agent.graph.check_groundedness")
def test_evaluation_node_un_grounded_escalates(mock_grounded):
    from app.agent.graph import evaluation_node
    mock_grounded.return_value = False

    state: AgentState = {
        "query": "test query",
        "session_id": "s1",
        "chat_history": [],
        "retrieved_chunks": [{"content": "c1"}],
        "context": "c1",
        "answer": "Hallucinated answer",
        "confidence": "",
        "escalate": False,
        "retry_count": 2,
        "error": None,
        "truncated": False,
    }

    res = evaluation_node(state)
    assert res["confidence"] == "low"
    assert res["escalate"] is True


