"""
runner.py
---------
Deterministic mock simulator.
Produces controlled output degradation per prompt version × query category.
Zero external dependencies — no real LLM calls.

Design principle:
  This is NOT random mocking. Each degradation function simulates
  a specific real failure mode caused by instruction conflicts in the prompt.

Failure modes simulated:
  v2 + simple_intent  → overreasoning_noise (CoT bleeds into rewritten_query)
  v2 + negation       → slight instruction friction (minor degradation)
  v3 + negation       → instruction_conflict (doc routing intercepts negation)
  v3 + aggregation    → numeric_scope_collapse (tabular routing misfires)
  v4 + simple_intent  → overreasoning_noise + schema drift (worst case)
  v4 + negation       → instruction_conflict (severe, both changes compound)
  v4 + multi_hop      → benefits_from_cot (genuine improvement)
  comparison (all)    → missing_comparative_anchor (known broken, all versions)
"""

import re


# ── INTENT CORRECT OUTPUTS ───────────────────────────────────────────────────

def _correct_output(query: dict) -> dict:
    """Baseline correct output — schema valid, intent correct, clean."""
    return {
        "intent": query["expected_intent"],
        "confidence": 0.91,
        "query_type": query.get("expected_query_type", "simple"),
        "rewritten_query": _clean_rewrite(query["query"]),
    }


def _clean_rewrite(query_text: str) -> str:
    """Minimal clean rewrite — no reasoning noise."""
    return query_text.strip().rstrip("?").rstrip(".").lower() + " [classified]"


# ── FAILURE MODE SIMULATORS ──────────────────────────────────────────────────

def _overreasoning_noise(query: dict) -> dict:
    """
    Simulates CoT instruction bleed into rewritten_query.
    The intent key is correct but rewritten_query is polluted with reasoning trace.
    Pattern checks fail on expected concise output patterns.
    Guard checks fire on 'step' and 'therefore' keywords.
    """
    return {
        "intent": query["expected_intent"],
        "confidence": 0.73,
        "query_type": query.get("expected_query_type", "simple"),
        "rewritten_query": (
            f"Step 1: Analyze the query '{query['query']}'. "
            f"Step 2: Identify the core intent. "
            f"Step 3: Therefore, the user is asking about {query['query'].lower()} "
            f"and I will reason through this carefully before classifying."
        ),
    }


def _overreasoning_severe(query: dict) -> dict:
    """
    v4 version: CoT + doc routing combined.
    Adds doc_type field but intent confidence collapses.
    Pattern checks fail; guard fires on 'step' tokens.
    """
    return {
        "intent": query["expected_intent"],
        "confidence": 0.51,
        "query_type": query.get("expected_query_type", "simple"),
        "rewritten_query": (
            f"Step 1: Check document type for '{query['query']}'. "
            f"Step 2: No tabular/policy/PDF markers found. "
            f"Step 3: Reason through intent step by step. "
            f"Therefore: {query['query'].lower()} — classified after full reasoning chain."
        ),
        "doc_type": "general",
    }


def _instruction_conflict_moderate(query: dict) -> dict:
    """
    v3 negation: doc routing priority intercepts negation keyword.
    Intent is misclassified ~50% of the time — simulated as wrong intent on half.
    Pattern for negation keywords is lost in rewrite.
    """
    return {
        "intent": "policy_lookup",  # WRONG — should be negation_check
        "confidence": 0.68,
        "query_type": "complex",
        "rewritten_query": (
            f"Document routing check applied. "
            f"Query '{query['query']}' routed to policy_doc type. "
            f"Negation context noted but deferred to document handler."
        ),
        "doc_type": "policy_doc",
    }


def _instruction_conflict_severe(query: dict) -> dict:
    """
    v4 negation: CoT + doc routing both active.
    Intent misclassified as ambiguous. Confidence very low.
    Pattern checks fail. Guard fires on CoT traces.
    """
    return {
        "intent": "ambiguous",  # WRONG — should be negation_check
        "confidence": 0.39,
        "query_type": "complex",
        "rewritten_query": (
            f"Step 1: Scan for document type signals in '{query['query']}'. "
            f"Step 2: Negation keyword detected — but document routing takes priority. "
            f"Step 3: Therefore classifying as ambiguous pending document context resolution."
        ),
        "doc_type": "policy_doc",
    }


def _numeric_scope_collapse(query: dict) -> dict:
    """
    v3/v4 aggregation: tabular routing misfires on numeric queries.
    Intent correct but doc_type='tabular' added; confidence drops.
    """
    return {
        "intent": query["expected_intent"],
        "confidence": 0.69,
        "query_type": "complex",
        "rewritten_query": (
            f"Numeric/tabular data query detected: '{query['query']}'. "
            f"Routing to tabular document handler."
        ),
        "doc_type": "tabular",
    }


def _missing_comparative_anchor(query: dict) -> dict:
    """
    All versions: comparison queries fail — known broken from QUL article.
    Intent is misclassified as fact_retrieval. Comparative patterns absent.
    """
    return {
        "intent": "fact_retrieval",  # WRONG — should be comparison
        "confidence": 0.61,
        "query_type": "complex",
        "rewritten_query": f"Retrieve information about: {query['query'].lower()}",
    }


def _cot_improvement(query: dict) -> dict:
    """
    v2/v4 multi-hop: CoT genuinely helps complex reasoning chains.
    All checks pass; confidence high. This is the FALSE IMPROVEMENT source.
    """
    return {
        "intent": query["expected_intent"],
        "confidence": 0.96,
        "query_type": "complex",
        "rewritten_query": (
            f"Multi-step reasoning applied to: '{query['query']}'. "
            f"Intent resolved through chain-of-thought classification."
        ),
        "doc_type": "general",
    }


def _v3_aggregation_improvement(query: dict) -> dict:
    """v3 aggregation: slight improvement from doc routing (tabular routing helps)."""
    return {
        "intent": query["expected_intent"],
        "confidence": 0.82,
        "query_type": "complex",
        "rewritten_query": f"Aggregation query over tabular data: {query['query'].lower()}",
        "doc_type": "tabular",
    }



def _no_cot_multihop_failure(query: dict) -> dict:
    """
    v1 baseline: without chain-of-thought, complex multi-condition queries
    are misclassified as fact_retrieval. The model cannot reason through
    conditional chains without explicit reasoning instructions.
    This is the PROBLEM that CoT solves — and why v4 shows improvement on multi_hop.
    """
    return {
        "intent": "fact_retrieval",  # WRONG — should be multi_hop_reasoning
        "confidence": 0.64,
        "query_type": "complex",
        "rewritten_query": f"retrieve information about: {query['query'].lower()} [classified]",
    }


def _edge_low_confidence(query: dict) -> dict:
    """
    v1 baseline: without CoT, ambiguous queries receive over-confident classification.
    Model picks the nearest intent instead of flagging ambiguity.
    """
    return {
        "intent": "fact_retrieval",  # WRONG — should be ambiguous
        "confidence": 0.78,
        "query_type": "simple",
        "rewritten_query": f"retrieve information about: {query['query'].lower()} [classified]",
    }

# ── ROUTING TABLE ─────────────────────────────────────────────────────────────

def simulate_output(prompt_version: str, query: dict) -> dict:
    """
    Route query to the correct degradation simulator based on
    prompt version × query category.

    This is the deterministic degradation model that produces
    the benchmark numbers in the article.
    """
    version = prompt_version.strip()
    category = query.get("category", "")

    # ── COMPARISON: broken across ALL versions ─────────────────────────────
    if category == "comparison":
        return _missing_comparative_anchor(query)

    # ── V1 BASELINE ──────────────────────────────────────────────────────
    # Without CoT, complex multi-hop queries fail: model cannot reason
    # through conditional chains and defaults to fact_retrieval.
    # Without explicit ambiguity handling, edge queries are over-classified.
    if version == "v1":
        if category == "multi_hop":
            return _no_cot_multihop_failure(query)
        if category == "edge_ambiguous":
            qnum = int(re.search(r'\d+', query["id"]).group())
            if qnum in (1, 2, 3):  # 3 of 4 edge queries over-classified
                return _edge_low_confidence(query)
        return _correct_output(query)

    # ── V2: CoT added ─────────────────────────────────────────────────────
    if version == "v2":
        if category == "simple_intent":
            return _overreasoning_noise(query)
        if category == "multi_hop":
            return _cot_improvement(query)
        if category == "negation":
            # Minor friction — 2 of 6 fail
            qnum = int(re.search(r'\d+', query["id"]).group())
            if qnum in (2, 5):
                return _instruction_conflict_moderate(query)
            return _correct_output(query)
        return _correct_output(query)

    # ── V3: Doc routing added ─────────────────────────────────────────────
    if version == "v3":
        if category == "negation":
            # 3 of 6 misclassified by routing priority
            qnum = int(re.search(r'\d+', query["id"]).group())
            if qnum in (1, 3, 5):
                return _instruction_conflict_moderate(query)
            return _correct_output(query)
        if category == "aggregation":
            return _v3_aggregation_improvement(query)
        if category == "simple_intent":
            # Mild degradation — routing check on simple queries adds noise
            qnum = int(re.search(r'\d+', query["id"]).group())
            if qnum in (3, 7):
                return _overreasoning_noise(query)
            return _correct_output(query)
        return _correct_output(query)

    # ── V4: CoT + Doc routing combined ────────────────────────────────────
    if version == "v4":
        if category == "simple_intent":
            # 2 of 10 fail: overreasoning severe on the shortest, most direct queries
            # longer simple queries partially survive the CoT noise
            qnum = int(re.search(r'\d+', query["id"]).group())
            if qnum in (1, 3):
                return _overreasoning_severe(query)
            return _correct_output(query)
        if category == "negation":
            # Severe: 4 of 6 fail (instruction conflict compounded)
            qnum = int(re.search(r'\d+', query["id"]).group())
            if qnum in (1, 2, 4, 5):
                return _instruction_conflict_severe(query)
            return _correct_output(query)
        if category == "multi_hop":
            # All 6 pass — genuine CoT benefit on complex queries
            return _cot_improvement(query)
        if category == "aggregation":
            # Slight improvement from tabular routing
            return _v3_aggregation_improvement(query)
        return _correct_output(query)

    # Fallback
    return _correct_output(query)
