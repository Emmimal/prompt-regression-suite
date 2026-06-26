"""
reporter.py
-----------
Generates the terminal regression report.
Zero external dependencies — pure string formatting.

Output sections:
  1. Per-version category table
  2. Baseline vs Candidate diff (for each non-baseline version)
  3. VERDICT with False Improvement detection
"""

from regression_suite.scorer import ScoringResult, RegressionFlag

# Terminal width for report formatting
WIDTH = 72
SEPARATOR = "=" * WIDTH
THIN = "-" * WIDTH

# Category display order and labels
CATEGORY_ORDER = [
    "simple_intent",
    "negation",
    "aggregation",
    "multi_hop",
    "comparison",
    "edge_ambiguous",
]

CATEGORY_LABELS = {
    "simple_intent":  "simple_intent    ",
    "negation":       "negation         ",
    "aggregation":    "aggregation      ",
    "multi_hop":      "multi_hop        ",
    "comparison":     "comparison       ",
    "edge_ambiguous": "edge_ambiguous   ",
}

FAILURE_MODES = {
    "simple_intent":  "overreasoning_noise",
    "negation":       "instruction_conflict",
    "aggregation":    "numeric_scope_collapse",
    "multi_hop":      "benefits_from_cot",
    "comparison":     "missing_comparative_anchor [KNOWN FAILURE]",
    "edge_ambiguous": "false_confidence",
}


def _arrow(delta: float) -> str:
    if delta > 0.5:
        return "▲"
    if delta < -0.5:
        return "▼"
    return " "


def _flag_label(flag: RegressionFlag) -> str:
    if flag.is_critical:
        return "[REGRESSION — CRITICAL]"
    return "[REGRESSION]"


def print_full_report(
    baseline: ScoringResult,
    candidates: list[ScoringResult],
    output_file: str = None,
) -> str:
    """
    Build and print the full regression report.
    Optionally writes to output_file.
    Returns the report as a string.
    """
    lines = []

    def add(line: str = ""):
        lines.append(line)

    # ── HEADER ────────────────────────────────────────────────────────────────
    add(SEPARATOR)
    add("  PROMPT REGRESSION SUITE — FULL REPORT")
    add(f"  Baseline: {baseline.prompt_version}  |  Candidates: "
        + ", ".join(c.prompt_version for c in candidates))
    add(SEPARATOR)

    # ── PER-VERSION CATEGORY TABLE ────────────────────────────────────────────
    add()
    add("  CATEGORY SCORES BY PROMPT VERSION")
    add(THIN)

    # Header row
    versions = [baseline] + candidates
    header = f"  {'Category':<22}"
    for sr in versions:
        header += f"  {sr.prompt_version:>8}"
    add(header)
    add(THIN)

    for cat in CATEGORY_ORDER:
        row = f"  {CATEGORY_LABELS.get(cat, cat):<22}"
        for sr in versions:
            cs = sr.category_scores.get(cat)
            pct = f"{cs.score_pct:.1f}%" if cs else "  N/A "
            row += f"  {pct:>8}"
        add(row)

    add(THIN)

    # Overall row
    overall_row = f"  {'OVERALL':<22}"
    for sr in versions:
        overall_row += f"  {sr.overall_score_pct:>7.1f}%"
    add(overall_row)
    add()

    # ── PER-CANDIDATE DIFF REPORTS ────────────────────────────────────────────
    for candidate in candidates:
        add(SEPARATOR)
        add(f"  DIFF REPORT: {baseline.prompt_version} → {candidate.prompt_version}")
        add(SEPARATOR)
        add()

        for cat in CATEGORY_ORDER:
            base_cs = baseline.category_scores.get(cat)
            cand_cs = candidate.category_scores.get(cat)

            if not base_cs or not cand_cs:
                continue

            delta = cand_cs.score_pct - base_cs.score_pct
            arrow = _arrow(delta)
            delta_str = f"{arrow} {abs(delta):.1f}%"

            # Check for regression flag
            flag_str = ""
            for flag in candidate.regression_flags:
                if flag.category == cat:
                    flag_str = f"  {_flag_label(flag)}"
                    break

            # Known failure annotation for comparison
            known_str = ""
            if cat == "comparison":
                known_str = "  [KNOWN FAILURE]"

            add(f"  {CATEGORY_LABELS.get(cat, cat):<22}"
                f"  {base_cs.score_pct:>6.1f}%"
                f"  →  {cand_cs.score_pct:>6.1f}%"
                f"   {delta_str:<10}"
                f"{flag_str}{known_str}")

        add()
        overall_delta = candidate.overall_score_pct - baseline.overall_score_pct
        overall_arrow = _arrow(overall_delta)
        add(f"  {'OVERALL':<22}  {baseline.overall_score_pct:>6.1f}%"
            f"  →  {candidate.overall_score_pct:>6.1f}%"
            f"   {overall_arrow} {abs(overall_delta):.1f}%")

        add()

        # ── VERDICT ───────────────────────────────────────────────────────────
        add(SEPARATOR)
        add(f"  VERDICT: {baseline.prompt_version} → {candidate.prompt_version}")
        add(SEPARATOR)

        if candidate.false_improvement_detected:
            add()
            add("  ⚠  FALSE IMPROVEMENT DETECTED")
            add()
            add(f"  {candidate.false_improvement_reason}")
            add()
            add("  Critical regressions:")
            for flag in candidate.regression_flags:
                if flag.is_critical:
                    mode = FAILURE_MODES.get(flag.category, "unknown")
                    add(f"    • {flag.category:<20} "
                        f"{flag.baseline_pct:.1f}% → {flag.candidate_pct:.1f}%  "
                        f"▼ {abs(flag.delta_pct):.1f}%")
                    add(f"      Failure mode: {mode}")
            add()
            add("  STATUS:  ✗  DO NOT PROMOTE TO PRODUCTION")

        elif candidate.regression_flags:
            add()
            add("  ✗  REGRESSIONS DETECTED")
            add()
            for flag in candidate.regression_flags:
                mode = FAILURE_MODES.get(flag.category, "unknown")
                add(f"    • {flag.category:<20} ▼ {abs(flag.delta_pct):.1f}%")
                add(f"      Failure mode: {mode}")
            add()
            add("  STATUS:  ✗  DO NOT PROMOTE TO PRODUCTION")

        else:
            add()
            add("  ✓  NO REGRESSIONS DETECTED")
            add()
            add("  STATUS:  ✓  SAFE TO PROMOTE")

        add()

    # ── FAILURE MODE LEGEND ───────────────────────────────────────────────────
    add(SEPARATOR)
    add("  FAILURE MODE LEGEND")
    add(SEPARATOR)
    for cat in CATEGORY_ORDER:
        mode = FAILURE_MODES.get(cat, "—")
        add(f"  {CATEGORY_LABELS.get(cat, cat):<22}  {mode}")
    add(SEPARATOR)

    report = "\n".join(lines)
    print(report)

    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n  Report saved to: {output_file}")

    return report
