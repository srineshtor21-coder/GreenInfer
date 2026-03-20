"""
GreenInfer Complexity Scorer
Analyzes prompt difficulty to inform model routing decisions.
Uses linguistic and structural features: token length, Shannon entropy,
task classification signals, and reasoning depth indicators.
No training required - engineered features with calibrated weights.
"""

import math
import re
from dataclasses import dataclass


@dataclass
class ComplexityResult:
    score: float            # 0.0 to 1.0
    score_100: int          # 0 to 100 (for display)
    label: str              # "Low" / "Medium" / "High" / "Very High"
    tier: str               # "small" / "medium" / "large"
    features: dict          # breakdown of what contributed
    accuracy_req: str       # "Low" / "Moderate" / "High" / "Critical"


def tokenize(text: str) -> list:
    return re.findall(r"\b\w+\b", text.lower())


def shannon_entropy(tokens: list) -> float:
    if not tokens:
        return 0.0
    freq = {}
    for t in tokens:
        freq[t] = freq.get(t, 0) + 1
    n = len(tokens)
    entropy = 0.0
    for count in freq.values():
        p = count / n
        entropy -= p * math.log2(p)
    return entropy


def score_prompt(text: str, mode: str = "balanced") -> ComplexityResult:
    tokens = tokenize(text)
    n = len(tokens)

    if n == 0:
        return ComplexityResult(0.0, 0, "Low", "small", {}, "Low")

    length_score   = min(n / 120, 0.20)
    entropy        = shannon_entropy(tokens)
    entropy_score  = min(entropy / 7.0, 0.18)

    reasoning_patterns = [
        r"\bwhy\b", r"\banalyze\b", r"\bexplain\b", r"\bcompare\b",
        r"\bevaluate\b", r"\bcritique\b", r"\bargue\b", r"\bprove\b",
        r"\bimplications?\b", r"\bconsequences?\b", r"\brelationship\b",
        r"\bdifference between\b", r"\bhow does\b", r"\bwhat causes\b",
        r"\beffect of\b", r"\bimpact of\b",
    ]
    reasoning_hits  = sum(1 for p in reasoning_patterns if re.search(p, text.lower()))
    reasoning_score = min(reasoning_hits * 0.055, 0.22)

    code_patterns = [
        r"\bfunction\b", r"\bdef \b", r"\bclass \b", r"\bimport \b",
        r"\breturn\b", r"\balgorithm\b", r"\bcode\b", r"\bprogram\b",
        r"\bdebug\b", r"\bimplement\b", r"\bapi\b", r"\bsql\b",
        r"\brecursion\b", r"```", r"\bpython\b", r"\bjavascript\b",
    ]
    code_hits  = sum(1 for p in code_patterns if re.search(p, text.lower()))
    code_score = min(code_hits * 0.05, 0.20)

    math_patterns = [
        r"\bintegral\b", r"\bderivative\b", r"\bequation\b", r"\bsolve\b",
        r"\bcalculate\b", r"\bproof\b", r"\btheorem\b", r"\bmatrix\b",
        r"\bstatistic\b", r"\bprobability\b", r"\bquantum\b", r"\bcalculus\b",
    ]
    math_hits  = sum(1 for p in math_patterns if re.search(p, text.lower()))
    math_score = min(math_hits * 0.045, 0.18)

    multi_patterns = [
        r"\bstep by step\b", r"\bfirst.*then\b", r"\bmultiple\b",
        r"\blist all\b", r"\bcomprehensive\b", r"\bdetailed\b",
        r"\bin depth\b", r"\bthoroughly\b", r"\bessay\b",
    ]
    multi_hits  = sum(1 for p in multi_patterns if re.search(p, text.lower()))
    multi_score = min(multi_hits * 0.04, 0.12)

    score = min(
        length_score + entropy_score + reasoning_score +
        code_score + math_score + multi_score,
        1.0
    )
    score = round(score, 4)
    score_100 = round(score * 100)

    if score < 0.25:   label, accuracy_req = "Low",       "Low"
    elif score < 0.50: label, accuracy_req = "Medium",    "Moderate"
    elif score < 0.75: label, accuracy_req = "High",      "High"
    else:              label, accuracy_req = "Very High",  "Critical"

    tier = _route_tier(score, mode)

    features = {
        "length_tokens": n, "entropy": round(entropy, 3),
        "reasoning_signals": reasoning_hits, "code_signals": code_hits,
        "math_signals": math_hits, "multistep_signals": multi_hits,
        "length_score": round(length_score, 3),
        "entropy_score": round(entropy_score, 3),
        "reasoning_score": round(reasoning_score, 3),
        "code_score": round(code_score, 3),
        "math_score": round(math_score, 3),
        "multi_score": round(multi_score, 3),
    }

    return ComplexityResult(score, score_100, label, tier, features, accuracy_req)


def _route_tier(score: float, mode: str) -> str:
    if mode == "eco":
        if score < 0.45: return "small"
        if score < 0.72: return "medium"
        return "large"
    elif mode == "performance":
        if score < 0.18: return "medium"
        return "large"
    else:
        if score < 0.30: return "small"
        if score < 0.62: return "medium"
        return "large"


if __name__ == "__main__":
    tests = [
        ("What is the capital of France?",                                              "balanced"),
        ("Write a Python merge sort implementation",                                    "balanced"),
        ("Analyze the philosophical implications of quantum entanglement on reality",   "balanced"),
        ("Hi",                                                                          "eco"),
        ("Compare Keynesian vs Austrian economics with historical examples",            "balanced"),
        ("Explain step by step how HTTPS encryption works",                             "balanced"),
    ]
    print(f"{'Prompt':<55} {'Score':>5} {'Label':<10} {'Tier':<7}")
    print("-" * 82)
    for prompt, mode in tests:
        r = score_prompt(prompt, mode)
        print(f"{prompt[:54]:<55} {r.score_100:>5} {r.label:<10} {r.tier:<7}")
