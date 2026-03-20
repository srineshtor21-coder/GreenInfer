"""
GreenInfer Backend API
Deployed as a Hugging Face Space (Docker SDK).
Exposes the GreenInfer pipeline over HTTP so the website chatbot can call it.

Endpoints:
    GET  /           status check
    GET  /health     detailed component health
    POST /analyze    optimize + score a prompt (no LLM call)
    POST /chat       full pipeline: optimize -> score -> cascade -> response + metrics
"""

import os
import time
import logging
import sys

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("greeninfer.backend")

app = FastAPI(
    title="GreenInfer API",
    description="Green Orchestration Framework for energy-efficient LLM inference",
    version="0.1.0"
)

# CORS - required for GitHub Pages (or any browser) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # restrict to your domain once live
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy-load heavy components at startup
_orchestrator = None
_optimizer_status = "not loaded"
_groq_status = "not loaded"


def get_orchestrator():
    global _orchestrator, _optimizer_status, _groq_status
    if _orchestrator is not None:
        return _orchestrator

    # Add parent dir to path so greeninfer package is importable
    sys.path.insert(0, "/app")

    from greeninfer import GreenInfer

    hf_model = os.environ.get("HF_MODEL_NAME", "sirenice/GreenPromptsOptimizer")
    groq_key  = os.environ.get("GROQ_API_KEY", "")

    try:
        _orchestrator = GreenInfer(
            optimizer_model=hf_model,
            groq_api_key=groq_key,
            mode="balanced",
            carbon_aware=False,
        )
        _optimizer_status = f"loaded: {hf_model}"
        _groq_status = "ready" if groq_key else "no key set"
        logger.info("GreenInfer orchestrator initialized")
    except Exception as e:
        logger.error(f"Orchestrator init failed: {e}")
        raise HTTPException(status_code=500, detail=f"Init failed: {e}")

    return _orchestrator


@app.on_event("startup")
async def startup():
    try:
        get_orchestrator()
    except Exception as e:
        logger.warning(f"Startup init failed (will retry on first request): {e}")


# Request/response schemas

class PromptRequest(BaseModel):
    prompt: str
    mode: str = "balanced"


class AnalyzeResponse(BaseModel):
    original_prompt: str
    optimized_prompt: str
    original_tokens: int
    optimized_tokens: int
    tokens_saved: int
    reduction_pct: int
    complexity_score: float
    complexity_score_100: int
    complexity_label: str
    accuracy_req: str
    recommended_tier: str
    optimizer_used: bool


class ChatResponse(BaseModel):
    response: str
    model_tier: str
    model_name: str
    complexity_score: float
    complexity_score_100: int
    complexity_label: str
    original_tokens: int
    optimized_tokens: int
    tokens_saved: int
    reduction_pct: int
    energy_mwh: float
    co2_grams: float
    escalations: int
    cascade_path: list
    baseline_energy_mwh: float
    energy_saved_pct: int
    optimizer_used: bool
    latency_ms: int


# Endpoints

@app.get("/")
def root():
    return {
        "status": "GreenInfer API running",
        "optimizer": _optimizer_status,
        "groq": _groq_status,
        "version": "0.1.0",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "optimizer": _optimizer_status,
        "groq": _groq_status,
    }


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: PromptRequest):
    """Optimize and score a prompt without calling any LLM."""
    gi = get_orchestrator()
    original_tokens = len(req.prompt.split())
    optimized, used = gi._optimize_prompt(req.prompt)
    optimized_tokens = len(optimized.split())
    tokens_saved = max(0, original_tokens - optimized_tokens)
    reduction_pct = round((tokens_saved / original_tokens) * 100) if original_tokens > 0 else 0

    from greeninfer.complexity_scorer import score_prompt
    complexity = score_prompt(req.prompt, req.mode)

    return AnalyzeResponse(
        original_prompt=req.prompt,
        optimized_prompt=optimized,
        original_tokens=original_tokens,
        optimized_tokens=optimized_tokens,
        tokens_saved=tokens_saved,
        reduction_pct=reduction_pct,
        complexity_score=complexity.score,
        complexity_score_100=complexity.score_100,
        complexity_label=complexity.label,
        accuracy_req=complexity.accuracy_req,
        recommended_tier=complexity.tier,
        optimizer_used=used,
    )


@app.post("/chat", response_model=ChatResponse)
def chat(req: PromptRequest):
    """Full pipeline: optimize -> score -> cascade inference -> response + metrics."""
    gi = get_orchestrator()

    try:
        result = gi.chat(req.prompt, mode=req.mode)
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=503, detail=str(e))

    return ChatResponse(
        response=result.response,
        model_tier=result.model_tier,
        model_name=result.model_id,
        complexity_score=result.complexity_score,
        complexity_score_100=result.complexity_score_100,
        complexity_label=result.complexity_label,
        original_tokens=result.original_tokens,
        optimized_tokens=result.optimized_tokens,
        tokens_saved=result.tokens_saved,
        reduction_pct=result.reduction_pct,
        energy_mwh=result.energy_mwh,
        co2_grams=result.co2_grams,
        escalations=result.escalations,
        cascade_path=result.cascade_path,
        baseline_energy_mwh=result.baseline_energy_mwh,
        energy_saved_pct=result.energy_saved_pct,
        optimizer_used=result.optimizer_used,
        latency_ms=result.latency_ms,
    )
