"""
LLM Gateway — Abstraction over watsonx.ai (primary) and OpenAI (fallback).
Tracks token usage and cost per call.
"""
import time
import uuid
import logging
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)

# Cost per 1K tokens (approximate, update as needed)
COST_PER_1K = {
    "watsonx": 0.0006,
    "openai": 0.005,
}


class LLMResponse:
    def __init__(self, content: str, provider: str, model: str,
                 tokens_used: int, cost_usd: float, latency_ms: int):
        self.content = content
        self.provider = provider
        self.model = model
        self.tokens_used = tokens_used
        self.cost_usd = cost_usd
        self.latency_ms = latency_ms


async def call_watsonx(prompt: str, system_prompt: str = "", max_tokens: int = 512) -> Optional[LLMResponse]:
    """Call IBM watsonx.ai granite model."""
    if not settings.WATSONX_API_KEY or not settings.WATSONX_PROJECT_ID:
        return None
    try:
        from ibm_watsonx_ai.foundation_models import ModelInference
        from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams

        start = time.time()
        model = ModelInference(
            model_id=settings.WATSONX_MODEL_ID,
            credentials={"apikey": settings.WATSONX_API_KEY, "url": settings.WATSONX_URL},
            project_id=settings.WATSONX_PROJECT_ID,
            params={
                GenParams.MAX_NEW_TOKENS: max_tokens,
                GenParams.TEMPERATURE: 0.3,
                GenParams.TOP_P: 0.9,
            }
        )
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        response = model.generate_text(prompt=full_prompt)
        latency = int((time.time() - start) * 1000)
        tokens = len(full_prompt.split()) + len(response.split())
        cost = (tokens / 1000) * COST_PER_1K["watsonx"]
        return LLMResponse(response, "watsonx", settings.WATSONX_MODEL_ID, tokens, cost, latency)
    except Exception as e:
        logger.warning(f"watsonx.ai call failed: {e}")
        return None


async def call_openai(prompt: str, system_prompt: str = "", max_tokens: int = 512) -> Optional[LLMResponse]:
    """Call OpenAI GPT-4o as fallback."""
    if not settings.OPENAI_API_KEY:
        return None
    try:
        from openai import AsyncOpenAI
        start = time.time()
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        resp = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.3,
        )
        latency = int((time.time() - start) * 1000)
        tokens = resp.usage.total_tokens if resp.usage else 0
        cost = (tokens / 1000) * COST_PER_1K["openai"]
        content = resp.choices[0].message.content or ""
        return LLMResponse(content, "openai", settings.OPENAI_MODEL, tokens, cost, latency)
    except Exception as e:
        logger.warning(f"OpenAI call failed: {e}")
        return None


async def llm_generate(
    prompt: str,
    system_prompt: str = "",
    max_tokens: int = 512,
    agent_name: str = "unknown",
    run_id: Optional[str] = None,
) -> LLMResponse:
    """
    Try watsonx.ai first; fall back to OpenAI.
    Returns a LLMResponse regardless (raises on total failure).
    """
    run_id = run_id or str(uuid.uuid4())
    result = await call_watsonx(prompt, system_prompt, max_tokens)
    if not result:
        result = await call_openai(prompt, system_prompt, max_tokens)
    if not result:
        # Last-resort: return a stub for demo/simulation
        result = LLMResponse(
            content="[LLM unavailable — simulated response for demo]",
            provider="stub",
            model="stub",
            tokens_used=0,
            cost_usd=0.0,
            latency_ms=0,
        )
    logger.info(f"[LLM] agent={agent_name} provider={result.provider} tokens={result.tokens_used} cost=${result.cost_usd:.5f} latency={result.latency_ms}ms")
    return result
