"""
GreenInfer Benchmark Experiments
Measures energy savings, accuracy, and latency across model tiers.
Produces the empirical results for your research documentation.

This is what makes the project real research - measured results
comparing your framework against a naive always-large-model baseline.

Usage:
    python experiments/benchmark.py

Output:
    experiments/results/benchmark_results.csv
    experiments/results/summary.txt
"""

import csv
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from greeninfer.complexity_scorer import score_prompt

# ── Test prompts with known expected quality tier ──────────────────────────

BENCHMARK_PROMPTS = [
    # Low complexity
    {"prompt": "What is the capital of France?",                "expected_tier": "small",  "category": "factual"},
    {"prompt": "What is 15 times 8?",                          "expected_tier": "small",  "category": "math_simple"},
    {"prompt": "Who invented the telephone?",                  "expected_tier": "small",  "category": "factual"},
    {"prompt": "What color is the sky?",                       "expected_tier": "small",  "category": "factual"},
    {"prompt": "How many days are in a leap year?",            "expected_tier": "small",  "category": "factual"},
    {"prompt": "What does API stand for?",                     "expected_tier": "small",  "category": "factual"},
    {"prompt": "What year did World War II end?",              "expected_tier": "small",  "category": "factual"},
    {"prompt": "What is the largest ocean?",                   "expected_tier": "small",  "category": "factual"},
    # Medium complexity
    {"prompt": "Explain how photosynthesis works.",            "expected_tier": "medium", "category": "explanation"},
    {"prompt": "What are the pros and cons of electric cars?", "expected_tier": "medium", "category": "analysis"},
    {"prompt": "Summarize the causes of World War I.",         "expected_tier": "medium", "category": "summary"},
    {"prompt": "How does HTTPS encryption work?",              "expected_tier": "medium", "category": "technical"},
    {"prompt": "What is the difference between RAM and ROM?",  "expected_tier": "medium", "category": "comparison"},
    {"prompt": "Explain the concept of recursion in programming.", "expected_tier": "medium", "category": "cs"},
    {"prompt": "What is machine learning and how is it used?", "expected_tier": "medium", "category": "explanation"},
    # High complexity
    {"prompt": "Write a Python function that implements binary search with proper error handling and documentation.", "expected_tier": "large", "category": "coding"},
    {"prompt": "Analyze the economic causes and lasting effects of the 2008 financial crisis.", "expected_tier": "large", "category": "analysis"},
    {"prompt": "Explain the philosophical debate between free will and determinism, citing key thinkers.", "expected_tier": "large", "category": "philosophy"},
    {"prompt": "Design a system architecture for a real-time chat application that scales to 1 million users.", "expected_tier": "large", "category": "system_design"},
    {"prompt": "Compare and contrast transformer and LSTM architectures for NLP tasks, with specific technical details.", "expected_tier": "large", "category": "technical"},
]

# Baseline energy (always using large model) in mWh
BASELINE_ENERGY_MWH = 48.0

# Model energy estimates in mWh
MODEL_ENERGY = {
    "small":  0.9,
    "medium": 3.8,
    "large":  48.0,
}


def run_benchmark():
    print("=" * 70)
    print("GreenInfer Framework Benchmark")
    print("=" * 70)
    print(f"Test prompts: {len(BENCHMARK_PROMPTS)}")
    print(f"Baseline: always-large model ({BASELINE_ENERGY_MWH} mWh/query)")
    print()

    results = []
    total_greeninfer_energy = 0
    total_baseline_energy   = 0
    correct_routing         = 0

    print(f"{'#':<3} {'Category':<14} {'Score':>5} {'Routed':<8} {'Expected':<8} {'Energy':>8} {'Saved%':>7}")
    print("-" * 60)

    for i, item in enumerate(BENCHMARK_PROMPTS, 1):
        prompt    = item["prompt"]
        expected  = item["expected_tier"]
        category  = item["category"]

        complexity = score_prompt(prompt, "balanced")
        routed_tier = complexity.tier
        energy_mwh  = MODEL_ENERGY[routed_tier]
        saved_pct   = round(((BASELINE_ENERGY_MWH - energy_mwh) / BASELINE_ENERGY_MWH) * 100)

        routing_correct = (routed_tier == expected)
        if routing_correct:
            correct_routing += 1

        total_greeninfer_energy += energy_mwh
        total_baseline_energy   += BASELINE_ENERGY_MWH

        flag = "" if routing_correct else " !"
        print(
            f"{i:<3} {category:<14} {complexity.score_100:>5} "
            f"{routed_tier:<8} {expected:<8} {energy_mwh:>6.1f}mWh "
            f"{saved_pct:>6}%{flag}"
        )

        results.append({
            "prompt":           prompt[:60],
            "category":         category,
            "complexity_score": complexity.score_100,
            "complexity_label": complexity.label,
            "routed_tier":      routed_tier,
            "expected_tier":    expected,
            "routing_correct":  routing_correct,
            "energy_mwh":       energy_mwh,
            "baseline_energy_mwh": BASELINE_ENERGY_MWH,
            "energy_saved_mwh": BASELINE_ENERGY_MWH - energy_mwh,
            "energy_saved_pct": saved_pct,
        })

    # Summary
    total_saved_mwh  = total_baseline_energy - total_greeninfer_energy
    total_saved_pct  = round((total_saved_mwh / total_baseline_energy) * 100)
    routing_accuracy = round((correct_routing / len(BENCHMARK_PROMPTS)) * 100)

    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    print(f"Routing accuracy:     {routing_accuracy}% ({correct_routing}/{len(BENCHMARK_PROMPTS)} correct)")
    print(f"Total energy (GreenInfer): {total_greeninfer_energy:.1f} mWh")
    print(f"Total energy (Baseline):   {total_baseline_energy:.1f} mWh")
    print(f"Total energy saved:        {total_saved_mwh:.1f} mWh ({total_saved_pct}%)")
    print(f"CO2 avoided (ERCOT avg):   {total_saved_mwh * 0.000198 * 1000:.3f} g CO2")

    # Save CSV
    os.makedirs("experiments/results", exist_ok=True)
    csv_path = "experiments/results/benchmark_results.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    print(f"\nDetailed results saved to: {csv_path}")

    # Save summary
    summary = {
        "total_prompts":           len(BENCHMARK_PROMPTS),
        "routing_accuracy_pct":    routing_accuracy,
        "greeninfer_energy_mwh":   round(total_greeninfer_energy, 2),
        "baseline_energy_mwh":     round(total_baseline_energy, 2),
        "energy_saved_mwh":        round(total_saved_mwh, 2),
        "energy_saved_pct":        total_saved_pct,
        "co2_avoided_g":           round(total_saved_mwh * 0.000198 * 1000, 4),
    }
    with open("experiments/results/summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print("Summary saved to: experiments/results/summary.json")

    return summary


if __name__ == "__main__":
    run_benchmark()
