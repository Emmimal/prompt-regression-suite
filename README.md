Detect prompt regressions before they reach production — per-category accuracy scoring, deterministic validation, and False Improvement detection. Pure Python, zero dependencies.

# prompt-regression-suite

A pure-Python framework for detecting prompt regressions before they reach production — per-category accuracy scoring, deterministic validation, and False Improvement detection in one pipeline.

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Read the full write-up on Towards Data Science → [Prompt Engineering Fails Over Time — Prompt Regression Is Why](https://towardsdatascience.com/author/emmimalp-alexander/)

---

## The Problem

When you update a system prompt to handle a new edge case, you are changing the behaviour of every query type the prompt already handles — not just the ones you were thinking about.

Most teams catch this through user reports. This framework catches it before the prompt ships.

The False Improvement pattern is the specific failure this suite was built to detect: a prompt change improves overall accuracy while collapsing a critical query category. The aggregate metric goes up. The prompt is broken.

```
  CATEGORY SCORES BY PROMPT VERSION
------------------------------------------------------------------------
  Category                      v1        v2        v3        v4
------------------------------------------------------------------------
  simple_intent             100.0%     40.0%     80.0%     90.0%
  negation                  100.0%     66.7%     50.0%     33.3%
  aggregation               100.0%    100.0%    100.0%    100.0%
  multi_hop                   0.0%    100.0%    100.0%    100.0%
  comparison                  0.0%      0.0%      0.0%      0.0%
  edge_ambiguous             25.0%    100.0%    100.0%    100.0%
------------------------------------------------------------------------
  OVERALL                    57.5%     60.0%     67.5%     67.5%

  VERDICT: v1 → v4

  ⚠  FALSE IMPROVEMENT DETECTED

  Overall score improved by 10.0% but critical categories regressed: [negation]

  Critical regressions:
    • negation   100.0% → 33.3%  ▼ 66.7%
      Failure mode: instruction_conflict

  STATUS:  ✗  DO NOT PROMOTE TO PRODUCTION
```

---

## What It Does

```
prompts/          golden_set/
prompt_v*.yaml    queries.json
      |                |
      └──── loader.py ─┘
                  |
             runner.py
          (simulate output per
           prompt × query)
                  |
           validator.py
           (4 deterministic
            checks per query)
                  |
            scorer.py
          (per-category score +
     False Improvement detection)
                  |
           reporter.py
         (terminal diff table +
          VERDICT per candidate)
                  |
       regression_report.txt
```

Five modules, one entry point, zero dependencies.

| Module | Job |
|--------|-----|
| `loader.py` | Loads prompt YAML files and golden query set (pure stdlib) |
| `runner.py` | Deterministic mock simulator — controlled degradation per prompt version × query category |
| `validator.py` | Four-check deterministic validator: schema, pattern, intent, guard |
| `scorer.py` | Per-category accuracy scoring and False Improvement detection |
| `reporter.py` | Terminal diff table and VERDICT per candidate prompt |

---

## Installation

```bash
git clone https://github.com/Emmimal/prompt-regression-suite.git
cd prompt-regression-suite
```

No dependencies. No `pip install`. Python 3.8+ only.

---

## Quick Start

```bash
python run_regression.py
```

Output is printed to terminal and saved to `results/regression_report.txt`.

---

## Project Structure

```
prompt-regression-suite/
├── run_regression.py           # single entry point
├── regression_suite/
│   ├── __init__.py
│   ├── loader.py               # pure stdlib YAML + JSON loader
│   ├── validator.py            # 4-check deterministic validator
│   ├── runner.py               # deterministic mock simulator
│   ├── scorer.py               # per-category scoring + False Improvement detection
│   └── reporter.py             # terminal report generator
├── prompts/
│   ├── prompt_v1.yaml          # baseline: clean intent classification
│   ├── prompt_v2.yaml          # +chain-of-thought (introduces overreasoning_noise)
│   ├── prompt_v3.yaml          # +document routing (introduces instruction_conflict)
│   └── prompt_v4.yaml          # both combined (False Improvement source)
├── golden_set/
│   └── queries.json            # 40 queries with validation signatures
└── results/
    └── regression_report.txt   # generated on every run
```

---

## The Golden Set

40 queries across six intent categories, each chosen to expose a specific failure mode.

| Category | N | Failure Mode Targeted |
|----------|---|-----------------------|
| simple_intent | 10 | overreasoning_noise |
| comparison | 8 | missing_comparative_anchor |
| aggregation | 6 | numeric_scope_collapse |
| negation | 6 | instruction_conflict |
| multi_hop | 6 | benefits_from_cot |
| edge_ambiguous | 4 | false_confidence |

Each query carries a validation signature — not a reference answer, but a set of deterministic constraints:

```json
{
  "id": "NQ_01",
  "query": "Which products are not covered under the warranty policy?",
  "category": "negation",
  "expected_intent": "negation_check",
  "expected_schema_keys": ["intent", "confidence", "query_type", "rewritten_query"],
  "expected_patterns": ["not covered", "warranty"],
  "must_not_contain": ["I cannot", "As an AI"],
  "failure_mode": "instruction_conflict"
}
```

---

## The Validator

Four deterministic checks per query output. No LLM-as-judge. No variance between runs.

```python
# 1. Schema check: required keys present in output dict
schema_pass = all(k in output for k in expected_schema_keys)

# 2. Pattern check: expected patterns present in output text
pattern_pass = all(re.search(p, output_text) for p in expected_patterns)

# 3. Intent check: classified intent matches expected label
intent_pass = output.get("intent") == expected_intent

# 4. Guard check: must_not_contain strings are absent
guard_pass = not any(g in output_text for g in must_not_contain)
```

A query passes only if all four checks pass. Category score is `passed / total`.

---

## False Improvement Detection

```python
REGRESSION_THRESHOLD = 0.10
CRITICAL_CATEGORIES = {"simple_intent", "negation"}

# Fires when overall score improves but a critical category regresses
if overall_improved and critical_regressions:
    candidate.false_improvement_detected = True
```

`CRITICAL_CATEGORIES` is system-specific. Change it to match your production traffic distribution.

---

## Adapting for Your System

The validator and scorer are system-agnostic. To adapt this for your own prompts:

**1. Write your golden set.** For each query category your system handles, write 5–10 queries designed to expose the failure mode specific to that category. Write the validation signature before the query — knowing what correct behaviour looks like is what makes you choose the right test case.

**2. Write your simulator.** Read your prompt changelog. Every instruction added after the baseline is a potential conflict. For each conflict, write a failure function that produces output reflecting that conflict. The act of writing the simulator forces you to map your prompt's failure surface.

**3. Set your critical categories.** Look at your production query distribution. Which categories handle the most traffic? Which failures are most costly? Those are your critical categories.

**4. Set your threshold.** The default 10% drop is a starting point. For high-stakes systems, tighten to 5%. The threshold is a parameter, not a principle.

**5. Run before every prompt change.** The suite takes under two seconds. There is no justification for running it after.

---

## Performance

Tested on Python 3.12, Windows 11, CPU only.

| Operation | Result |
|-----------|--------|
| Queries processed | 40 |
| Prompt versions tested | 4 |
| Total run time | under 2 seconds |
| External dependencies | 0 |
| API calls | 0 |

---

## Honest Limitations

The deterministic simulator reflects real failure patterns from one specific system. A different system with different instruction conflicts will have different failure points. The framework is portable. The degradation model is not — you need to write your own.

The comparison category scores 0.0% across all four prompt versions. This is a known architectural limitation: the current prompt has no comparative anchor resolution step. It is included in the benchmark unchanged and annotated as `[KNOWN FAILURE]` in every diff report.

Token estimation in the simulator uses heuristics, not a tokenizer. This has no effect on the regression logic — it only affects confidence score simulation fidelity.

---

## License

MIT

---

## Related Articles

- [Prompt Engineering Fails Over Time — Prompt Regression Is Why](https://towardsdatascience.com/prompt-regression) — the article this codebase was built for
- [RAG Isn't Enough — I Built the Missing Context Layer That Makes LLM Systems Work](https://towardsdatascience.com/rag-isnt-enough-i-built-the-missing-context-layer-that-makes-llm-systems-work/) — the RAG system this prompt suite was built on top of
