"""
GreenInfer Complexity Dataset Builder
Generates synthetic labeled training data for the complexity classifier.

Creates prompt-label pairs across 4 complexity levels using diverse
templates. You can also add real prompts from your chatbot logs later
to improve the model over time.

Usage:
    python build_complexity_dataset.py
    
Output:
    data/complexity_dataset.json
"""

import json
import os
import random
from complexity_scorer import score_prompt   # uses rule-based scorer to auto-label

random.seed(42)

# ── Template pools per complexity level ──────────────────────────────────────

LOW_TEMPLATES = [
    "What is the capital of {country}?",
    "What is {number} plus {number2}?",
    "Who invented {invention}?",
    "What color is {object}?",
    "When was {person} born?",
    "What does {abbreviation} stand for?",
    "What language is spoken in {country}?",
    "What is the boiling point of water?",
    "How many days are in a year?",
    "What is the speed of light?",
    "Hi, how are you?",
    "Hello",
    "What time is it?",
    "What is 2 times 8?",
    "What year did World War II end?",
    "What is the largest planet in our solar system?",
    "What is the chemical symbol for gold?",
    "Who wrote Romeo and Juliet?",
    "What is the square root of 144?",
    "Name the seven continents.",
]

MEDIUM_TEMPLATES = [
    "Explain how {topic} works in simple terms.",
    "Summarize the main points of {topic}.",
    "What are the advantages and disadvantages of {topic}?",
    "Describe the process of {process}.",
    "What is the difference between {concept1} and {concept2}?",
    "Give me a brief overview of {topic}.",
    "How does {technology} affect {domain}?",
    "Write a short paragraph about {topic}.",
    "What are the key features of {topic}?",
    "Can you explain {concept} in a few sentences?",
    "What causes {phenomenon}?",
    "List the main benefits of {topic}.",
    "How do you {task} in Python?",
    "Explain the concept of {cs_concept} briefly.",
    "What is the purpose of {tool} in software development?",
]

HIGH_TEMPLATES = [
    "Write a Python function that implements {algorithm} with proper error handling.",
    "Explain the philosophical implications of {topic} and how it challenges {belief}.",
    "Analyze the causes and effects of {historical_event} and its lasting impact.",
    "Compare and contrast {concept1} and {concept2}, citing specific examples.",
    "Design a system architecture for {system_type} that handles {requirement}.",
    "Explain step by step how {technology} works at a technical level.",
    "Write an essay analyzing the impact of {topic} on modern society.",
    "How would you implement a {data_structure} from scratch in Python?",
    "Evaluate the strengths and weaknesses of {approach} for solving {problem}.",
    "Describe a comprehensive strategy for {goal}, including potential obstacles.",
]

VERY_HIGH_TEMPLATES = [
    "Provide a thorough analysis of {complex_topic}, covering historical context, current state, and future implications, with concrete examples.",
    "Write a complete implementation of {complex_system} in Python, including proper error handling, documentation, and unit tests.",
    "Argue both for and against {controversial_topic}, then synthesize a nuanced conclusion based on the evidence.",
    "Design and explain a complete machine learning pipeline for {ml_problem}, from data preprocessing to model evaluation.",
    "Explain in depth how {advanced_tech} works, comparing multiple approaches, their tradeoffs, and when to use each.",
    "Write a comprehensive technical specification for {product_type} including architecture, APIs, data models, and scaling considerations.",
    "Analyze the relationship between {discipline1} and {discipline2}, drawing on specific research and historical examples to support your argument.",
]

# Fill-in values
FILL = {
    "country":          ["France", "Japan", "Brazil", "Germany", "Australia", "India"],
    "number":           ["5", "12", "7", "100", "42"],
    "number2":          ["3", "8", "15", "6", "9"],
    "invention":        ["the telephone", "the internet", "the airplane", "penicillin"],
    "object":           ["the sky", "grass", "snow", "the sun"],
    "person":           ["Einstein", "Marie Curie", "Shakespeare", "Newton"],
    "abbreviation":     ["NASA", "CPU", "DNA", "HTTP", "AI"],
    "topic":            ["photosynthesis", "machine learning", "blockchain", "climate change",
                         "neural networks", "quantum computing", "CRISPR", "microservices"],
    "process":          ["DNA replication", "photosynthesis", "gradient descent", "TCP/IP handshake"],
    "concept1":         ["machine learning", "supervised learning", "REST", "SQL"],
    "concept2":         ["deep learning", "unsupervised learning", "GraphQL", "NoSQL"],
    "technology":       ["AI", "blockchain", "cloud computing", "5G"],
    "domain":           ["healthcare", "education", "finance", "transportation"],
    "phenomenon":       ["inflation", "climate change", "neural plasticity", "market crashes"],
    "task":             ["sort a list", "read a file", "make an API call", "parse JSON"],
    "cs_concept":       ["recursion", "object-oriented programming", "concurrency", "caching"],
    "tool":             ["Docker", "Git", "Kubernetes", "Redis"],
    "algorithm":        ["merge sort", "binary search", "Dijkstra's algorithm", "quicksort"],
    "belief":           ["free will", "determinism", "objective reality", "human uniqueness"],
    "historical_event": ["the French Revolution", "World War II", "the Industrial Revolution"],
    "system_type":      ["distributed messaging", "real-time analytics", "recommendation engine"],
    "requirement":      ["high availability", "low latency", "horizontal scaling"],
    "data_structure":   ["linked list", "binary search tree", "hash table", "priority queue"],
    "approach":         ["microservices architecture", "monolithic design", "event-driven design"],
    "problem":          ["scaling web services", "real-time data processing", "distributed consensus"],
    "goal":             ["reducing AI energy consumption", "improving model efficiency", "scaling to 1M users"],
    "complex_topic":    ["the geopolitical implications of AI development",
                         "the ethics of genetic engineering",
                         "the economic effects of automation on labor markets"],
    "complex_system":   ["a green AI orchestration framework",
                         "a distributed rate limiter",
                         "a real-time collaborative editor"],
    "controversial_topic": ["universal basic income", "nuclear energy expansion",
                            "AI regulation", "open-source AI models"],
    "ml_problem":       ["predicting energy consumption from text features",
                         "sentiment classification",
                         "document summarization"],
    "advanced_tech":    ["transformer attention mechanisms", "gradient checkpointing",
                         "model quantization", "speculative decoding"],
    "product_type":     ["AI chatbot platform", "green compute scheduler", "LLM router"],
    "discipline1":      ["computer science", "economics", "cognitive science"],
    "discipline2":      ["environmental science", "philosophy", "neuroscience"],
}

def fill_template(template: str) -> str:
    result = template
    for key, values in FILL.items():
        placeholder = f"{{{key}}}"
        if placeholder in result:
            result = result.replace(placeholder, random.choice(values))
    return result

def build_dataset(n_per_tier: int = 120) -> list:
    examples = []
    all_templates = [
        (LOW_TEMPLATES,       "Low"),
        (MEDIUM_TEMPLATES,    "Medium"),
        (HIGH_TEMPLATES,      "High"),
        (VERY_HIGH_TEMPLATES, "Very High"),
    ]
    for templates, expected_label in all_templates:
        count = 0
        attempts = 0
        while count < n_per_tier and attempts < n_per_tier * 10:
            attempts += 1
            tmpl   = random.choice(templates)
            prompt = fill_template(tmpl)
            result = score_prompt(prompt, "balanced")
            examples.append({
                "prompt":    prompt,
                "label":     result.label,
                "score":     result.score,
                "score_100": result.score_100,
                "tier":      result.tier,
                "expected_label": expected_label,
            })
            count += 1

    random.shuffle(examples)
    return examples


if __name__ == "__main__":
    print("Building GreenInfer complexity dataset...")
    os.makedirs("data", exist_ok=True)

    n = 150
    examples = build_dataset(n_per_tier=n)

    with open("data/complexity_dataset.json", "w") as f:
        json.dump(examples, f, indent=2)

    # Stats
    from collections import Counter
    labels = Counter(e["label"] for e in examples)
    print(f"\nTotal examples: {len(examples)}")
    print("Label distribution:")
    for label, count in sorted(labels.items()):
        print(f"  {label:<12}: {count}")

    print(f"\nDataset saved to data/complexity_dataset.json")
    print("Next: python train_complexity.py")
