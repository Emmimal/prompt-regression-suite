"""
validator.py
------------
Deterministic output validation.
Zero external dependencies — pure re + dict + isinstance.

Three validation modes:
  SCHEMA   — required keys present in output dict
  PATTERN  — expected patterns present in output text (re.search)
  INTENT   — classified intent matches expected intent label
  GUARD    — must_not_contain strings are absent from output text
"""

import re
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    query_id: str
    schema_pass: bool
    pattern_pass: bool
    intent_pass: bool
    guard_pass: bool
    schema_failures: list[str] = field(default_factory=list)
    pattern_failures: list[str] = field(default_factory=list)
    guard_violations: list[str] = field(default_factory=list)
    detected_intent: str = ""
    expected_intent: str = ""

    @property
    def passed(self) -> bool:
        return self.schema_pass and self.pattern_pass and self.intent_pass and self.guard_pass

    @property
    def score(self) -> float:
        """Fractional score 0.0–1.0 across four checks."""
        checks = [self.schema_pass, self.pattern_pass, self.intent_pass, self.guard_pass]
        return sum(checks) / len(checks)


class QueryValidator:
    """
    Validates a simulated model output against a golden query signature.
    All validation is deterministic — no LLM-as-judge.
    """

    def validate(self, output: dict, query: dict) -> ValidationResult:
        """
        Args:
            output: dict produced by the mock simulator
            query:  golden query dict from queries.json

        Returns:
            ValidationResult with pass/fail per check type
        """
        query_id = query["id"]
        expected_intent = query["expected_intent"]
        expected_keys = query.get("expected_schema_keys", [])
        expected_patterns = query.get("expected_patterns", [])
        must_not_contain = query.get("must_not_contain", [])

        # ── SCHEMA CHECK ─────────────────────────────────────────────────────
        schema_failures = [k for k in expected_keys if k not in output]
        schema_pass = len(schema_failures) == 0

        # ── FLATTEN OUTPUT TO TEXT for pattern/guard checks ───────────────────
        output_text = " ".join(str(v) for v in output.values()).lower()

        # ── PATTERN CHECK ─────────────────────────────────────────────────────
        pattern_failures = [
            p for p in expected_patterns
            if not re.search(re.escape(p.lower()), output_text)
        ]
        pattern_pass = len(pattern_failures) == 0

        # ── INTENT CHECK ──────────────────────────────────────────────────────
        detected_intent = output.get("intent", "")
        intent_pass = detected_intent == expected_intent

        # ── GUARD CHECK ───────────────────────────────────────────────────────
        guard_violations = [
            g for g in must_not_contain
            if g.lower() in output_text
        ]
        guard_pass = len(guard_violations) == 0

        return ValidationResult(
            query_id=query_id,
            schema_pass=schema_pass,
            pattern_pass=pattern_pass,
            intent_pass=intent_pass,
            guard_pass=guard_pass,
            schema_failures=schema_failures,
            pattern_failures=pattern_failures,
            guard_violations=guard_violations,
            detected_intent=detected_intent,
            expected_intent=expected_intent,
        )
