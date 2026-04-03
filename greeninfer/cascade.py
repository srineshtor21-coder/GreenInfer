"""
GreenInfer Cascade Engine
Implements cascading model inference - tries the smallest viable model first,
escalates to larger models only when confidence is low.

This is the key mechanism that achieves energy savings even when the
complexity scorer makes imperfect routing decisions.
"""

import os
import time
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger("greeninfer.cascade")

LOW_CONFIDENCE_PHRASES = [
    "i'm not sure", "i cannot", "i don't know", "i am unable",
    "i lack", "unclear", "i apologize, but i don't",
    "beyond my knowledge", "i don't have enough information",
    "i cannot provide", "i'm unable to", "as an ai, i don't",
    "i don't have access", "i cannot determine"
]


@dataclass
class CascadeResult:
    response: str
    final_tier: str
    model_id: str
    escalations: int
    cascade_path: list[str]
    output_tokens: int
    latency_ms: int
    confidence_ok: bool


class CascadeEngine:
    """
    Attempts inference starting from the recommended tier and escalates
    upward if the response indicates low confidence.

    Example:
        engine = CascadeEngine(groq_client)
        result = engine.run(
            prompt="Explain general relativity",
            start_tier="small",
            registry=my_registry
        )
        print(result.response)
        print(f"Used {result.final_tier} after {result.escalations} escalations")
    """

    def __init__(self, groq_client=None, confidence_threshold: float = 0.6):
        """
        Args:
            groq_client:           Initialized Groq client (or None to skip)
            confidence_threshold:  Below this, escalate to next tier
        """
        self._groq = groq_client
        self.confidence_threshold = confidence_threshold

        self._system_prompt = (
            "You are GreenInfer, a knowledgeable and helpful AI assistant. "
            "Answer accurately and clearly. Be concise but complete. "
            "If you are unsure about something, say so explicitly."
        )

    def run(
        self,
        prompt: str,
        start_tier: str,
        registry,
        min_complexity: float = 0.15,
        carbon_budget_remaining: Optional[float] = None,
    ) -> CascadeResult:
        """
        Run cascade inference starting from start_tier.

        Args:
            prompt:                   The (already optimized) prompt to run
            start_tier:               Tier to start from ("small"/"medium"/"large")
            registry:                 ModelRegistry instance
            min_complexity:           Do not escalate if complexity is below this
            carbon_budget_remaining:  If set, skip tiers that would exceed budget
        """
        tiers = registry.tiers_from(start_tier)
        cascade_path = []
        escalations = 0
        start_time = time.time()

        for tier in tiers:
            config = registry.get(tier)
            if config is None:
                logger.warning(f"No config for tier {tier}, skipping")
                continue

            # Check carbon budget
            if carbon_budget_remaining is not None:
                if config.energy_mwh * config.co2_g_per_mwh > carbon_budget_remaining:
                    logger.info(f"Skipping {tier} - would exceed carbon budget")
                    continue

            cascade_path.append(tier)
            logger.info(f"Cascade: trying {tier} ({config.model_id})")

            try:
                response_text = self._call_model(prompt, config)
                output_tokens = len(response_text.split())
                latency_ms = round((time.time() - start_time) * 1000)

                # Decide whether to accept or escalate
                is_last_tier = (tier == tiers[-1])
                confidence_ok = self._check_confidence(response_text, prompt)

                should_escalate = (
                    not confidence_ok
                    and not is_last_tier
                    and min_complexity > 0.15   # never escalate truly trivial prompts
                )

                if should_escalate:
                    logger.info(f"Low confidence from {tier}, escalating")
                    escalations += 1
                    continue

                logger.info(
                    f"Cascade complete: {tier} | "
                    f"escalations={escalations} | "
                    f"latency={latency_ms}ms"
                )
                return CascadeResult(
                    response=response_text,
                    final_tier=tier,
                    model_id=config.model_id,
                    escalations=escalations,
                    cascade_path=cascade_path,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    confidence_ok=True,
                )

            except Exception as e:
                logger.error(f"Error calling {tier} ({config.model_id}): {e}")
                escalations += 1
                continue

        # All tiers failed or exhausted
        logger.error("All cascade tiers failed or exhausted")
        latency_ms = round((time.time() - start_time) * 1000)
        return CascadeResult(
            response="I was unable to generate a response. Please try again.",
            final_tier=tiers[-1] if tiers else start_tier,
            model_id="unknown",
            escalations=escalations,
            cascade_path=cascade_path,
            output_tokens=0,
            latency_ms=latency_ms,
            confidence_ok=False,
        )

    def _call_model(self, prompt: str, config) -> str:
        """Call the appropriate provider based on config."""
        if config.provider == "groq":
            return self._call_groq(prompt, config)
        elif config.provider == "openai":
            return self._call_openai(prompt, config)
        elif config.provider == "huggingface":
            return self._call_hf_inference(prompt, config)
        else:
            raise ValueError(f"Unsupported provider: {config.provider}")

    def _call_groq(self, prompt: str, config) -> str:
    import httpx, os
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set")
    
    r = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": config.model_id,
            "messages": [
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": config.max_tokens,
            "temperature": 0.7,
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

    def _call_openai(self, prompt: str, config) -> str:
        import openai
        api_key = os.environ.get(config.api_key_env)
        client = openai.OpenAI(api_key=api_key)
        completion = client.chat.completions.create(
            model=config.model_id,
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": prompt}
            ],
            max_tokens=config.max_tokens,
        )
        return completion.choices[0].message.content

    def _call_hf_inference(self, prompt: str, config) -> str:
        import httpx
        api_key = os.environ.get(config.api_key_env, "")
        url = f"https://api-inference.huggingface.co/models/{config.model_id}"
        headers = {"Authorization": f"Bearer {api_key}"}
        payload = {"inputs": prompt, "parameters": {"max_new_tokens": config.max_tokens}}
        r = httpx.post(url, json=payload, headers=headers, timeout=30)
        r.raise_for_status()
        result = r.json()
        if isinstance(result, list) and result:
            return result[0].get("generated_text", "")
        return str(result)

    def _check_confidence(self, response: str, prompt: str) -> bool:
        """
        Returns True if response seems confident enough to accept.
        Returns False if we should escalate to a bigger model.
        """
        text_lower = response.lower()

        # Check for explicit uncertainty phrases
        has_hedge = any(phrase in text_lower for phrase in LOW_CONFIDENCE_PHRASES)
        if has_hedge:
            return False

        # Response is suspiciously short for a substantive question
        prompt_words = len(prompt.split())
        response_words = len(response.split())
        if prompt_words > 5 and response_words < 8:
            return False

        return True
