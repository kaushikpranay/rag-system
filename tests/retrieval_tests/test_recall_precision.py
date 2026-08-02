import json
from pathlib import Path
import pytest

pytestmark = pytest.mark.integration


@pytest.mark.integration
def test_recall_precision():
    dir_path = Path(__file__).parent
    golden_set_path = dir_path / "golden_set.json"
    threshold_results_path = dir_path / "threshold_results.json"

    with open(golden_set_path, "r", encoding="utf-8") as f:
        golden_set = json.load(f)

    with open(threshold_results_path, "r", encoding="utf-8") as f:
        threshold_results = json.load(f)

    results_by_query = {
        item["query"]: item for item in threshold_results.get("details", [])
    }

    for item in golden_set:
        query = item["query"]
        min_acceptable_sim = item["min_acceptable_similarity"]

        assert query in results_by_query, (
            f"Query missing from threshold_results.json: '{query}'"
        )
        res = results_by_query[query]

        status = res.get("status")
        correct_sim = res.get("correct_similarity")

        assert status == "HIT", (
            f"Query '{query}' failed status check: expected 'HIT', got '{status}'"
        )

        assert correct_sim is not None and correct_sim >= min_acceptable_sim, (
            f"Query '{query}' failed similarity threshold: "
            f"actual similarity {correct_sim} < expected min_acceptable_similarity {min_acceptable_sim}"
        )


if __name__ == "__main__":
    test_recall_precision()
