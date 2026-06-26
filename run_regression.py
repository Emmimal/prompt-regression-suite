"""
run_regression.py
-----------------
Single entry point for the Prompt Regression Suite.

Usage:
    python run_regression.py

Zero external dependencies.
Python 3.8+ required.
"""

import sys
from pathlib import Path

# Resolve the directory containing this file (prompt-regression-suite/)
# and insert it at the front of sys.path so that `regression_suite` is
# always found regardless of PyCharm's working directory setting.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from regression_suite.loader import load_prompts, load_golden_set
from regression_suite.runner import simulate_output
from regression_suite.validator import QueryValidator
from regression_suite.scorer import Scorer
from regression_suite.reporter import print_full_report


PROMPTS_DIR      = str(_HERE / "prompts")
GOLDEN_SET_PATH  = str(_HERE / "golden_set" / "queries.json")
REPORT_PATH      = str(_HERE / "results" / "regression_report.txt")
BASELINE_VERSION = "v1"


def main():
    print("\n  Loading prompts...")
    prompts = load_prompts(PROMPTS_DIR)
    print(f"  Loaded {len(prompts)} prompt versions: {', '.join(sorted(prompts.keys()))}")

    print("  Loading golden set...")
    golden_queries = load_golden_set(GOLDEN_SET_PATH)
    print(f"  Loaded {len(golden_queries)} golden queries.\n")

    validator = QueryValidator()
    scorer = Scorer()
    scoring_results = {}

    for version in sorted(prompts.keys()):
        validation_results = []
        for query in golden_queries:
            output = simulate_output(version, query)
            vr = validator.validate(output, query)
            vr.query_id = query["id"]
            validation_results.append(vr)

        sr = scorer.score(version, validation_results)
        scoring_results[version] = sr

    baseline = scoring_results[BASELINE_VERSION]
    candidates = []
    for version in sorted(scoring_results.keys()):
        if version == BASELINE_VERSION:
            continue
        candidate = scorer.compare(baseline, scoring_results[version])
        candidates.append(candidate)

    print_full_report(baseline, candidates, output_file=REPORT_PATH)


if __name__ == "__main__":
    main()
