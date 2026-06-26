"""
scorer.py
---------
Per-category regression scoring and False Improvement detection.
Zero external dependencies.

Scoring logic:
  Each query produces a ValidationResult with .passed (bool).
  Category score = passed_count / total_count for that category.
  Regression = category score drops more than REGRESSION_THRESHOLD vs baseline.
  False Improvement = overall score improves AND >= 1 critical category regresses.
"""

from dataclasses import dataclass, field
from collections import defaultdict

REGRESSION_THRESHOLD = 0.10   # 10% drop from baseline = flagged regression
CRITICAL_CATEGORIES = {        # categories that must not regress
    "simple_intent",
    "negation",
}


@dataclass
class CategoryScore:
    category: str
    total: int
    passed: int

    @property
    def score(self) -> float:
        return self.passed / self.total if self.total > 0 else 0.0

    @property
    def score_pct(self) -> float:
        return self.score * 100


@dataclass
class RegressionFlag:
    category: str
    baseline_pct: float
    candidate_pct: float
    delta_pct: float
    is_critical: bool


@dataclass
class ScoringResult:
    prompt_version: str
    category_scores: dict[str, CategoryScore]
    overall_score: float
    overall_score_pct: float
    regression_flags: list[RegressionFlag] = field(default_factory=list)
    false_improvement_detected: bool = False
    false_improvement_reason: str = ""


class Scorer:
    """
    Computes per-category scores from validation results.
    Compares candidate against baseline and flags regressions.
    """

    def score(
        self,
        version: str,
        validation_results: list,   # list[ValidationResult]
    ) -> ScoringResult:
        """Build a ScoringResult from a list of ValidationResults."""
        by_category: dict[str, list] = defaultdict(list)
        for vr in validation_results:
            # Recover category from query_id prefix (SI_, CQ_, etc.)
            category = self._category_from_id(vr.query_id)
            by_category[category].append(vr)

        category_scores = {}
        total_passed = 0
        total_queries = len(validation_results)

        for cat, results in by_category.items():
            passed = sum(1 for r in results if r.passed)
            total_passed += passed
            category_scores[cat] = CategoryScore(
                category=cat,
                total=len(results),
                passed=passed,
            )

        overall = total_passed / total_queries if total_queries > 0 else 0.0

        return ScoringResult(
            prompt_version=version,
            category_scores=category_scores,
            overall_score=overall,
            overall_score_pct=overall * 100,
        )

    def compare(
        self,
        baseline: ScoringResult,
        candidate: ScoringResult,
    ) -> ScoringResult:
        """
        Attach regression flags to the candidate ScoringResult.
        Detect False Improvement pattern.
        Returns the candidate with flags populated.
        """
        flags = []
        critical_regressions = []

        for cat, cand_cat in candidate.category_scores.items():
            base_cat = baseline.category_scores.get(cat)
            if base_cat is None:
                continue

            delta = cand_cat.score - base_cat.score

            if delta < -REGRESSION_THRESHOLD:
                is_critical = cat in CRITICAL_CATEGORIES
                flag = RegressionFlag(
                    category=cat,
                    baseline_pct=base_cat.score_pct,
                    candidate_pct=cand_cat.score_pct,
                    delta_pct=delta * 100,
                    is_critical=is_critical,
                )
                flags.append(flag)
                if is_critical:
                    critical_regressions.append(flag)

        candidate.regression_flags = flags

        # ── FALSE IMPROVEMENT DETECTION ───────────────────────────────────
        overall_improved = candidate.overall_score > baseline.overall_score
        if overall_improved and critical_regressions:
            candidate.false_improvement_detected = True
            cats = ", ".join(f.category for f in critical_regressions)
            candidate.false_improvement_reason = (
                f"Overall score improved by "
                f"{(candidate.overall_score - baseline.overall_score) * 100:.1f}% "
                f"but critical categories regressed: [{cats}]"
            )

        return candidate

    @staticmethod
    def _category_from_id(query_id: str) -> str:
        prefix_map = {
            "SI": "simple_intent",
            "CQ": "comparison",
            "AQ": "aggregation",
            "NQ": "negation",
            "MH": "multi_hop",
            "EA": "edge_ambiguous",
        }
        prefix = query_id.split("_")[0]
        return prefix_map.get(prefix, "unknown")
