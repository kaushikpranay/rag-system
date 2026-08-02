"""
Generation Tests — LLM Out-of-Scope Refusal
File: tests/GENERATION TESTS/test_refusal.py
"""
import pytest


@pytest.mark.integration
@pytest.mark.skip(reason="requires live LLM/DB — run manually, not automated in CI")
def test_out_of_scope_refusal():
    """
    Manual Verification Test:
    Verify that the LLM correctly refuses out-of-scope questions (e.g., 'What is the capital of France?')
    using run_agent() against live Groq + RDS vector database, returning a polite refusal message.
    """
    pass
