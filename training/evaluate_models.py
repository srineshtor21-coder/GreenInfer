"""
GreenInfer - Model Evaluation Script
Evaluates the trained complexity classifier against the rule-based scorer.
Run after train_complexity.py to compare both approaches.

Usage:
    cd training
    python evaluate_models.py
"""

import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from greeninfer.complexity_scorer import score_prompt

CLASSIFIER_PATH = "../models/complexity_classifier"
DATA_PATH = "../data/complexity_dataset.json"

LABEL_MAP = {"Low": 0, "Medium": 1, "High": 2, "Very High": 3}
ID_TO_LABEL = {v: k for k, v in LABEL_MAP.items()}


def evaluate_rule_based(examples: list) -> dict:
    """Evaluate the rule-based complexity scorer on labeled examples."""
    correct = 0
    predictions = []
    actuals = []

    for ex in examples:
        result = score_prompt(ex["prompt"], "balanced")
        pred = result.label
        actual = ex["label"]
        predictions.append(pred)
        actuals.append(actual)
        if pred == actual:
            correct += 1

    accuracy = correct / len(examples)

    # Per-class accuracy
    per_class = {}
    for label in LABEL_MAP:
        label_examples = [e for e in examples if e["label"] == label]
        if not label_examples:
            continue
        label_correct = sum(
            1 for e in label_examples
            if score_prompt(e["prompt"], "balanced").label == label
        )
        per_class[label] = round(label_correct / len(label_examples), 3)

    return {
        "accuracy": round(accuracy, 4),
        "correct": correct,
        "total": len(examples),
        "per_class_accuracy": per_class,
    }


def evaluate_trained_classifier(examples: list) -> dict:
    """Evaluate the trained DistilBERT classifier if available."""
    try:
        import torch
        from transformers import DistilBertTokenizer, DistilBertForSequenceClassification
    except ImportError:
        print("transformers not installed. Skipping classifier evaluation.")
        return {}

    if not os.path.exists(CLASSIFIER_PATH):
        print(f"No trained classifier found at {CLASSIFIER_PATH}.")
        print("Run train_complexity.py first.")
        return {}

    print(f"Loading classifier from {CLASSIFIER_PATH}...")
    tokenizer = DistilBertTokenizer.from_pretrained(CLASSIFIER_PATH)
    model = DistilBertForSequenceClassification.from_pretrained(CLASSIFIER_PATH)
    model.eval()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    correct = 0
    predictions = []
    actuals = []

    with torch.no_grad():
        for ex in examples:
            enc = tokenizer(
                ex["prompt"],
                max_length=128,
                padding="max_length",
                truncation=True,
                return_tensors="pt"
            )
            input_ids = enc["input_ids"].to(device)
            attn_mask = enc["attention_mask"].to(device)

            outputs = model(input_ids=input_ids, attention_mask=attn_mask)
            pred_id = outputs.logits.argmax(dim=1).item()
            pred_label = ID_TO_LABEL[pred_id]
            actual = ex["label"]

            predictions.append(pred_label)
            actuals.append(actual)
            if pred_label == actual:
                correct += 1

    accuracy = correct / len(examples)

    per_class = {}
    for label in LABEL_MAP:
        label_indices = [i for i, e in enumerate(examples) if e["label"] == label]
        if not label_indices:
            continue
        label_correct = sum(1 for i in label_indices if predictions[i] == label)
        per_class[label] = round(label_correct / len(label_indices), 3)

    return {
        "accuracy": round(accuracy, 4),
        "correct": correct,
        "total": len(examples),
        "per_class_accuracy": per_class,
    }


def print_results(name: str, results: dict):
    if not results:
        return
    print(f"\n{name}")
    print("-" * 40)
    print(f"  Overall accuracy:  {results['accuracy'] * 100:.1f}%")
    print(f"  Correct:           {results['correct']} / {results['total']}")
    print("  Per-class accuracy:")
    for label, acc in results.get("per_class_accuracy", {}).items():
        bar = "#" * int(acc * 20)
        print(f"    {label:<12} {acc*100:>5.1f}%  {bar}")


def main():
    if not os.path.exists(DATA_PATH):
        print(f"Dataset not found at {DATA_PATH}")
        print("Run build_complexity_dataset.py first.")
        return

    with open(DATA_PATH) as f:
        examples = json.load(f)

    print("=" * 55)
    print("GreenInfer Complexity Model Evaluation")
    print("=" * 55)
    print(f"Dataset: {len(examples)} examples")

    label_dist = Counter(e["label"] for e in examples)
    print("Label distribution:")
    for label, count in sorted(label_dist.items()):
        print(f"  {label:<12}: {count}")

    rule_results       = evaluate_rule_based(examples)
    classifier_results = evaluate_trained_classifier(examples)

    print_results("Rule-Based Scorer (no training required)", rule_results)
    print_results("Trained DistilBERT Classifier", classifier_results)

    if rule_results and classifier_results:
        delta = classifier_results["accuracy"] - rule_results["accuracy"]
        direction = "+" if delta >= 0 else ""
        print(f"\nClassifier vs rule-based: {direction}{delta*100:.1f}%")

    # Save results
    os.makedirs("../experiments/results", exist_ok=True)
    output = {
        "rule_based": rule_results,
        "trained_classifier": classifier_results,
    }
    with open("../experiments/results/model_comparison.json", "w") as f:
        json.dump(output, f, indent=2)
    print("\nResults saved to experiments/results/model_comparison.json")


if __name__ == "__main__":
    main()
