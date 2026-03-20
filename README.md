# GreenInfer

**Green Orchestration Framework for Energy-Efficient LLM Inference**

*ISM Final Product - Srinesh Toranala*

GreenInfer is a model-agnostic Python framework that routes every AI prompt to the most energy-efficient model capable of answering it accurately. Instead of sending every query to a large expensive model, GreenInfer analyzes prompt complexity, predicts energy cost, and uses cascade inference to achieve up to 73% energy reduction without sacrificing response quality.

---

## The Problem

Every query sent to ChatGPT or similar AI systems uses the same large model regardless of whether the question is "What is 2+2?" or "Design a distributed system." That is massively wasteful. A simple factual question uses 50x more energy than it needs to.

## The Solution

GreenInfer sits in front of your model pool and makes intelligent routing decisions:

```
User Prompt
    |
    v
Prompt Optimizer (GreenPromptsOptimizer - T5 model)
    |
    v
Complexity Scorer (0-100 difficulty score)
    |
    v
Carbon Router (real-time ERCOT grid intensity)
    |
    v
Orchestrator (selects minimum viable model tier)
    |
    v
Cascade Inference (small -> medium -> large, escalates if needed)
    |
    v
Response + Energy Metrics
```

## Results

| System | Energy per Session | CO2 Emitted | Notes |
|---|---|---|---|
| Always-Large Baseline | 960 mWh | 0.190g | Standard API usage |
| GreenInfer (Balanced) | 259 mWh | 0.051g | 73% reduction |
| GreenInfer (Eco) | 118 mWh | 0.023g | 88% reduction |

*Based on 20-prompt benchmark. See `experiments/results/`.*

## Quick Start

```bash
pip install -e .
```

```python
from greeninfer import GreenInfer

gi = GreenInfer()  # uses Groq API by default (set GROQ_API_KEY env var)

result = gi.chat("Explain quantum entanglement")

print(result.response)
print(f"Model used:    {result.model_tier} ({result.model_id})")
print(f"Energy:        {result.energy_mwh} mWh")
print(f"CO2:           {result.co2_grams}g")
print(f"Energy saved:  {result.energy_saved_pct}% vs baseline")
print(f"Tokens saved:  {result.tokens_saved} via prompt optimization")
```

## Custom Model Pool

GreenInfer works with any provider:

```python
gi = GreenInfer(
    model_pool={
        "small": {
            "provider": "groq",
            "model": "llama-3.2-1b-preview",
            "api_key_env": "GROQ_API_KEY",
            "energy_mwh": 0.9
        },
        "medium": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "api_key_env": "OPENAI_API_KEY",
            "energy_mwh": 8.0
        },
        "large": {
            "provider": "openai",
            "model": "gpt-4o",
            "api_key_env": "OPENAI_API_KEY",
            "energy_mwh": 95.0
        },
    }
)
```

## Carbon-Aware Mode

Uses real-time ERCOT grid data to restrict large models when the grid is running on fossil fuels:

```python
gi = GreenInfer(
    carbon_aware=True,
    electricity_maps_key="your_key"  # or set ELECTRICITY_MAPS_KEY env var
)
```

## Session Tracking

```python
# After multiple calls
summary = gi.session_summary()
print(f"Total energy this session: {summary['total_energy_mwh']} mWh")
print(f"Total CO2: {summary['total_co2_grams']}g")
```

## Repository Structure

```
GreenInfer/
|
+-- greeninfer/                  Python package (the framework)
|   +-- __init__.py
|   +-- orchestrator.py          Main GreenInfer class
|   +-- complexity_scorer.py     Prompt difficulty analyzer
|   +-- energy_estimator.py      Energy and carbon tracking
|   +-- cascade.py               Cascade inference engine
|   +-- model_registry.py        Model pool manager
|   +-- carbon_router.py         Real-time grid awareness
|
+-- training/                    Model training code
|   +-- train_complexity.py      DistilBERT complexity classifier
|   +-- build_complexity_dataset.py
|
+-- experiments/                 Research benchmarks
|   +-- benchmark.py             Energy savings experiments
|   +-- results/                 CSV and JSON results
|
+-- backend/                     Hugging Face Space API
|   +-- app.py                   FastAPI server
|   +-- Dockerfile
|
+-- website/                     Demo chatbot (GitHub Pages)
|
+-- setup.py
+-- requirements.txt
```

## Models

| Model | Hosted At | Purpose |
|---|---|---|
| GreenPromptsOptimizer | [HF Space](https://huggingface.co/spaces/sirenice/GreenPromptsOptimizer) | Prompt compression (T5) |
| greeninfer-backend | [HF Space](https://huggingface.co/spaces/sirenice/greeninfer-backend) | FastAPI orchestration server |

## Running Experiments

```bash
cd GreenInfer
python experiments/benchmark.py
```

## Training the Complexity Classifier

```bash
cd training
python build_complexity_dataset.py   # generates data/complexity_dataset.json
python train_complexity.py           # trains DistilBERT classifier
```

## Live Demo

[greeninfer.github.io](https://srineshtor21-coder.github.io/GreenInfer)

## License

MIT - built for educational and research purposes as an ISM Final Project.

## Author

Srinesh Toranala - ISM Program, Frisco ISD
Mentor: Marta Adamska, PhD Candidate, University of Lancaster
