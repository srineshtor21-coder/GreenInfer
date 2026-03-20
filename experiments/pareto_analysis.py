"""
GreenInfer - Pareto Frontier Analysis
Plots the accuracy vs energy tradeoff across model tiers.
Identifies which routing decisions are Pareto-optimal.

Output:
    experiments/results/pareto_frontier.png
    experiments/results/pareto_data.json

Usage:
    python experiments/pareto_analysis.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Empirical accuracy and energy estimates per model tier
# Accuracy figures from published LLM benchmarks (MMLU, HellaSwag)
MODEL_DATA = [
    {
        "tier": "small",
        "model": "Llama 3.2 1B",
        "energy_mwh": 0.9,
        "accuracy_pct": 49.3,
        "latency_ms": 280,
        "params_b": 1.0,
    },
    {
        "tier": "medium-small",
        "model": "Phi-3 Mini 3.8B",
        "energy_mwh": 2.1,
        "accuracy_pct": 69.0,
        "latency_ms": 420,
        "params_b": 3.8,
    },
    {
        "tier": "medium",
        "model": "Llama 3.1 8B",
        "energy_mwh": 3.8,
        "accuracy_pct": 73.0,
        "latency_ms": 580,
        "params_b": 8.0,
    },
    {
        "tier": "medium-large",
        "model": "Mixtral 8x7B",
        "energy_mwh": 14.0,
        "accuracy_pct": 79.6,
        "latency_ms": 950,
        "params_b": 47.0,
    },
    {
        "tier": "large",
        "model": "Llama 3.3 70B",
        "energy_mwh": 48.0,
        "accuracy_pct": 86.0,
        "latency_ms": 2100,
        "params_b": 70.0,
    },
]


def find_pareto_frontier(points: list) -> list:
    """
    Returns points on the Pareto frontier for:
        maximize accuracy, minimize energy
    A point is Pareto-optimal if no other point is strictly
    better on both dimensions simultaneously.
    """
    pareto = []
    for p in points:
        dominated = any(
            q["accuracy_pct"] >= p["accuracy_pct"]
            and q["energy_mwh"] <= p["energy_mwh"]
            and (q["accuracy_pct"] > p["accuracy_pct"] or q["energy_mwh"] < p["energy_mwh"])
            for q in points
            if q is not p
        )
        if not dominated:
            pareto.append(p)
    return sorted(pareto, key=lambda x: x["energy_mwh"])


def compute_optimal_routing(
    complexity_score: float,
    min_accuracy: float,
    mode: str = "balanced"
) -> dict:
    """
    Given a complexity score and minimum acceptable accuracy,
    returns the Pareto-optimal model choice.
    """
    candidates = [m for m in MODEL_DATA if m["accuracy_pct"] >= min_accuracy]
    if not candidates:
        return MODEL_DATA[-1]

    if mode == "eco":
        return min(candidates, key=lambda m: m["energy_mwh"])
    elif mode == "performance":
        return max(candidates, key=lambda m: m["accuracy_pct"])
    else:
        frontier = find_pareto_frontier(candidates)
        if not frontier:
            return min(candidates, key=lambda m: m["energy_mwh"])
        # Choose the frontier point with best accuracy-to-energy ratio
        return max(frontier, key=lambda m: m["accuracy_pct"] / m["energy_mwh"])


def main():
    os.makedirs("experiments/results", exist_ok=True)

    pareto = find_pareto_frontier(MODEL_DATA)

    print("=" * 55)
    print("GreenInfer Pareto Frontier Analysis")
    print("=" * 55)
    print(f"\n{'Model':<22} {'Energy':>8} {'Accuracy':>10} {'Pareto':>8}")
    print("-" * 52)
    for m in MODEL_DATA:
        on_frontier = m in pareto
        marker = "YES" if on_frontier else "-"
        print(
            f"{m['model']:<22} {m['energy_mwh']:>6.1f}mWh "
            f"{m['accuracy_pct']:>8.1f}% {marker:>8}"
        )

    print(f"\nPareto-optimal points: {len(pareto)}/{len(MODEL_DATA)}")
    print("These are the models GreenInfer considers for routing.")

    # Routing examples
    print("\nExample routing decisions (balanced mode):")
    print(f"{'Min Accuracy':<16} {'Chosen Model':<22} {'Energy':>8}")
    print("-" * 48)
    for min_acc in [50, 65, 75, 82, 90]:
        chosen = compute_optimal_routing(0.5, min_acc, "balanced")
        print(f"{min_acc}%{'':<14} {chosen['model']:<22} {chosen['energy_mwh']:>6.1f}mWh")

    # Energy savings vs always using the largest model
    largest_energy = MODEL_DATA[-1]["energy_mwh"]
    print(f"\nEnergy savings vs always-large ({MODEL_DATA[-1]['model']}, {largest_energy} mWh):")
    for m in pareto[:-1]:
        saved_pct = round(((largest_energy - m["energy_mwh"]) / largest_energy) * 100)
        print(f"  {m['model']:<22}: -{saved_pct}% energy")

    # Save data
    output = {
        "all_models": MODEL_DATA,
        "pareto_frontier": pareto,
    }
    with open("experiments/results/pareto_data.json", "w") as f:
        json.dump(output, f, indent=2)
    print("\nData saved to experiments/results/pareto_data.json")

    # Try to plot if matplotlib is available
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches

        fig, ax = plt.subplots(figsize=(9, 6))
        ax.set_facecolor("#0b1214")
        fig.patch.set_facecolor("#080d0e")

        pareto_set = set(m["model"] for m in pareto)

        for m in MODEL_DATA:
            color = "#00ffa0" if m["model"] in pareto_set else "#4a7068"
            ax.scatter(m["energy_mwh"], m["accuracy_pct"], color=color, s=100, zorder=5)
            ax.annotate(
                m["model"],
                (m["energy_mwh"], m["accuracy_pct"]),
                textcoords="offset points",
                xytext=(8, 4),
                fontsize=8,
                color="#8ab5a8",
            )

        # Draw frontier line
        px = [m["energy_mwh"] for m in pareto]
        py = [m["accuracy_pct"] for m in pareto]
        ax.plot(px, py, color="#00ffa0", linewidth=1.5, linestyle="--", alpha=0.6, zorder=4)

        ax.set_xlabel("Energy (mWh per inference)", color="#8ab5a8")
        ax.set_ylabel("Accuracy (%)", color="#8ab5a8")
        ax.set_title("GreenInfer Pareto Frontier: Accuracy vs Energy", color="#e8f5f0", pad=14)
        ax.tick_params(colors="#4a7068")
        for spine in ax.spines.values():
            spine.set_edgecolor("#172226")

        green_patch = mpatches.Patch(color="#00ffa0", label="Pareto-optimal")
        grey_patch  = mpatches.Patch(color="#4a7068", label="Sub-optimal")
        ax.legend(handles=[green_patch, grey_patch], facecolor="#111c1e", labelcolor="#8ab5a8")

        plt.tight_layout()
        plt.savefig("experiments/results/pareto_frontier.png", dpi=150, facecolor=fig.get_facecolor())
        plt.close()
        print("Plot saved to experiments/results/pareto_frontier.png")
    except ImportError:
        print("matplotlib not installed - skipping plot. Install with: pip install matplotlib")


if __name__ == "__main__":
    main()
