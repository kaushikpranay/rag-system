import pytest
from unittest.mock import MagicMock, patch
from app.agent.graph import check_groundedness


@patch("app.agent.graph.Groq")
def test_check_groundedness_supported_yes(mock_groq):
    mock_client = MagicMock()
    mock_groq.return_value = mock_client

    mock_choice = MagicMock()
    mock_choice.message.content = "YES"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    answer = "The return policy is 30 days."
    context = "Our store allows returns within 30 days of purchase."

    result = check_groundedness(answer, context)

    assert result is True
    mock_client.chat.completions.create.assert_called_once()


@patch("app.agent.graph.Groq")
def test_check_groundedness_unsupported_no(mock_groq):
    mock_client = MagicMock()
    mock_groq.return_value = mock_client

    mock_choice = MagicMock()
    mock_choice.message.content = "NO"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    answer = "We offer free worldwide shipping."
    context = "Shipping costs $5 flat rate for domestic orders."

    result = check_groundedness(answer, context)

    assert result is False
    mock_client.chat.completions.create.assert_called_once()


@patch("app.agent.graph.Groq")
def test_check_groundedness_exception_fail_open(mock_groq):
    mock_client = MagicMock()
    mock_groq.return_value = mock_client

    mock_client.chat.completions.create.side_effect = RuntimeError("Groq API connection timeout")

    answer = "The return policy is 30 days."
    context = "Our store allows returns within 30 days of purchase."

    result = check_groundedness(answer, context)

    assert result is True
    mock_client.chat.completions.create.assert_called_once()
