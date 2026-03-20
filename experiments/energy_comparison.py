"""
GreenInfer - Energy Comparison Experiment
Compares energy consumption across three routing strategies:
  1. Always Large  - naive baseline, uses largest model every time
  2. Always Small  - aggressive baseline, always uses smallest model
  3. GreenInfer    - intelligent routing based on complexity

Output:
    experiments/results/energy_comparison.csv
    experiments/results/energy_comparison.png

Usage:
    python experiments/energy_comparison.py
"""

import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from greeninfer.complexity_scorer import score_prompt

# Energy per tier in mWh
ENERGY = {
    "small":  0.9,
    "medium": 3.8,
    "large":  48.0,
}

# Test set: prompts labeled by the minimum tier that can answer correctly
TEST_PROMPTS = [
    ("What is the capital of Japan?",                               "small"),
    ("How many planets are in the solar system?",                   "small"),
    ("What does HTTP stand for?",                                   "small"),
    ("What year was Python created?",                               "small"),
    ("What is 144 divided by 12?",                                  "small"),
    ("Who wrote Hamlet?",                                           "small"),
    ("What is the boiling point of water in Celsius?",              "small"),
    ("Name the primary colors.",                                    "small"),
    ("Explain how photosynthesis works.",                           "medium"),
    ("What are the main causes of the French Revolution?",          "medium"),
    ("Summarize how TCP/IP works.",                                 "medium"),
    ("What is the difference between RAM and a hard drive?",        "medium"),
    ("How does HTTPS protect data in transit?",                     "medium"),
    ("What is machine learning in simple terms?",                   "medium"),
    ("Explain recursion with an example.",                          "medium"),
    ("Write a Python function that reverses a string.",             "medium"),
    ("Analyze the economic impact of the 2008 financial crisis.",   "large"),
    ("Design a scalable microservices architecture for an e-commerce platform.", "large"),
    ("Write a complete binary search tree implementation in Python with all operations.", "large"),
    ("Compare transformer and LSTM architectures technically.",     "large"),
]


def run_comparison():
    print("=" * 65)
    print("GreenInfer Energy Comparison Experiment")
    print("=" * 65)
    print(f"Test set: {len(TEST_PROMPTS)} prompts\n")

    results = []
    totals = {"always_large": 0, "always_small": 0, "greeninfer": 0}

    print(f"{'Prompt':<50} {'GI Tier':<8} {'Min Tier':<8} {'GI mWh':>7} {'Large mWh':>10}")
    print("-" * 86)

    for prompt, min_tier in TEST_PROMPTS:
        complexity = score_prompt(prompt, "balanced")
        gi_tier    = complexity.tier

        gi_energy    = ENERGY[gi_tier]
        large_energy = ENERGY["large"]
        small_energy = ENERGY["small"]

        totals["always_large"] += large_energy
        totals["always_small"] += small_energy
        totals["greeninfer"]   += gi_energy

        correct_routing = (gi_tier == min_tier) or (
            ["small", "medium", "large"].index(gi_tier) >=
            ["small", "medium", "large"].index(min_tier)
        )

        results.append({
            "prompt":           prompt[:60],
            "min_tier":         min_tier,
            "gi_tier":          gi_tier,
            "complexity_score": complexity.score_100,
            "correct_routing":  correct_routing,
            "gi_energy_mwh":    gi_energy,
            "large_energy_mwh": large_energy,
            "small_energy_mwh": small_energy,
        })

        marker = "" if correct_routing else " !"
        print(
            f"{prompt[:49]:<50} {gi_tier:<8} {min_tier:<8} "
            f"{gi_energy:>6.1f} {large_energy:>9.1f}{marker}"
        )

    # Summary
    gi_savings_vs_large = round(
        ((totals["always_large"] - totals["greeninfer"]) / totals["always_large"]) * 100
    )
    gi_savings_vs_small = totals["greeninfer"] - totals["always_small"]

    correct_count  = sum(1 for r in results if r["correct_routing"])
    routing_acc    = round(correct_count / len(results) * 100)
    co2_avoided    = (totals["always_large"] - totals["greeninfer"]) * 0.000198 * 1000

    print("\n" + "=" * 65)
    print("SUMMARY")
    print("=" * 65)
    print(f"{'Strategy':<22} {'Total Energy':>14} {'vs Always-Large':>16}")
    print("-" * 54)
    print(f"{'Always Large':<22} {totals['always_large']:>11.1f} mWh {'baseline':>16}")
    print(f"{'Always Small':<22} {totals['always_small']:>11.1f} mWh "
          f"{round(((totals['always_large']-totals['always_small'])/totals['always_large'])*100):>14}%")
    print(f"{'GreenInfer':<22} {totals['greeninfer']:>11.1f} mWh {gi_savings_vs_large:>14}%")
    print(f"\nRouting accuracy: {routing_acc}% ({correct_count}/{len(results)})")
    print(f"CO2 avoided vs baseline: {co2_avoided:.3f}g CO2")
    print(f"Energy overhead vs always-small: +{gi_savings_vs_small:.1f} mWh "
          f"(cost of better accuracy on hard prompts)")

    # Save CSV
    os.makedirs("experiments/results", exist_ok=True)
    csv_path = "experiments/results/energy_comparison.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)

    summary = {
        "always_large_mwh":     round(totals["always_large"], 2),
        "always_small_mwh":     round(totals["always_small"], 2),
        "greeninfer_mwh":       round(totals["greeninfer"], 2),
        "savings_vs_large_pct": gi_savings_vs_large,
        "routing_accuracy_pct": routing_acc,
        "co2_avoided_g":        round(co2_avoided, 4),
    }
    with open("experiments/results/energy_comparison_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nCSV saved to {csv_path}")
    print("Summary saved to experiments/results/energy_comparison_summary.json")

    # Plot if matplotlib available
    try:
        import matplotlib.pyplot as plt
        import numpy as np

        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        fig.patch.set_facecolor("#080d0e")
        for ax in axes:
            ax.set_facecolor("#0b1214")
            ax.tick_params(colors="#4a7068")
            for spine in ax.spines.values():
                spine.set_edgecolor("#172226")

        # Bar chart - total energy
        strategies = ["Always\nLarge", "GreenInfer", "Always\nSmall"]
        energies   = [totals["always_large"], totals["greeninfer"], totals["always_small"]]
        colors     = ["#ff4d6d", "#00ffa0", "#00e5cc"]

        axes[0].bar(strategies, energies, color=colors, width=0.5)
        axes[0].set_ylabel("Total Energy (mWh)", color="#8ab5a8")
        axes[0].set_title("Energy Comparison", color="#e8f5f0")
        for i, (s, e) in enumerate(zip(strategies, energies)):
            axes[0].text(i, e + 5, f"{e:.0f}", ha="center", color="#8ab5a8", fontsize=9)

        # Per-prompt comparison
        prompt_labels = [f"P{i+1}" for i in range(len(results))]
        x = np.arange(len(results))
        width = 0.35
        gi_vals = [r["gi_energy_mwh"] for r in results]
        lg_vals = [r["large_energy_mwh"] for r in results]

        axes[1].bar(x - width/2, lg_vals, width, label="Always Large", color="#ff4d6d", alpha=0.7)
        axes[1].bar(x + width/2, gi_vals, width, label="GreenInfer",   color="#00ffa0", alpha=0.7)
        axes[1].set_xticks(x)
        axes[1].set_xticklabels(prompt_labels, fontsize=7, color="#4a7068")
        axes[1].set_ylabel("Energy (mWh)", color="#8ab5a8")
        axes[1].set_title("Per-Prompt Energy", color="#e8f5f0")
        axes[1].legend(facecolor="#111c1e", labelcolor="#8ab5a8", fontsize=8)

        plt.suptitle("GreenInfer Energy Savings", color="#e8f5f0", fontsize=13, y=1.01)
        plt.tight_layout()
        plt.savefig(
            "experiments/results/energy_comparison.png",
            dpi=150, facecolor=fig.get_facecolor(), bbox_inches="tight"
        )
        plt.close()
        print("Plot saved to experiments/results/energy_comparison.png")
    except ImportError:
        print("matplotlib not installed - skipping plot. Install with: pip install matplotlib")

    return summary


if __name__ == "__main__":
    run_comparison()
