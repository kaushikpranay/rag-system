"""
Regression Tests — Golden Set Baseline & Similarity Drift
File: tests/regression_tests/test_golden_set_regression.py
"""
import json
from pathlib import Path
import pytest


def _load_golden_set_and_results():
    dir_path = Path(__file__).parent.parent / "retrieval_tests"
    golden_set_path = dir_path / "golden_set.json"
    threshold_results_path = dir_path / "threshold_results.json"

    with open(golden_set_path, "r", encoding="utf-8") as f:
        golden_set = json.load(f)

    with open(threshold_results_path, "r", encoding="utf-8") as f:
        threshold_results = json.load(f)

    return golden_set, threshold_results


def test_golden_set_hit_rate_baseline():
    """
    Test: total hit_count across all queries must equal total query count
    (100% hit rate is the regression baseline — fail loudly with which queries missed if this drops).
    """
    golden_set, threshold_results = _load_golden_set_and_results()
    summary = threshold_results.get("summary", {})
    details = threshold_results.get("details", [])

    total_queries = summary.get("total_queries", len(golden_set))
    hit_count = summary.get("hit_count", 0)

    missed_queries = [
        item["query"] for item in details if item.get("status") != "HIT"
    ]

    assert hit_count == total_queries, (
        f"Regression failure: Hit rate dropped! {hit_count}/{total_queries} queries hit. "
        f"Missed queries: {missed_queries}"
    )
    assert len(missed_queries) == 0, f"Missed queries detected: {missed_queries}"


def test_avg_correct_similarity_baseline():
    """
    Test: avg_correct_similarity from threshold_results.json must not fall below 0.45
    (10% margin under current measured 0.5156) — this catches embedding/model drift.
    """
    _, threshold_results = _load_golden_set_and_results()
    summary = threshold_results.get("summary", {})

    avg_sim = summary.get("avg_correct_similarity", 0.0)
    baseline_min = 0.45

    assert avg_sim >= baseline_min, (
        f"Embedding drift failure: avg_correct_similarity ({avg_sim:.4f}) "
        f"fell below minimum baseline threshold ({baseline_min})"
    )
