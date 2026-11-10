"""
LangFuse observability client + Prometheus metrics + token cost tracker.
"""
import time
import uuid
import logging
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)

# ── Prometheus Metrics ────────────────────────────────────────────────────────
try:
    from prometheus_client import Counter, Histogram, Gauge, start_http_server

    agent_runs_total = Counter("agent_runs_total", "Total agent runs", ["agent_name", "success"])
    agent_latency_ms = Histogram("agent_latency_ms", "Agent latency in ms", ["agent_name"],
                                 buckets=[100, 250, 500, 1000, 2000, 5000, 10000])
    llm_tokens_total = Counter("llm_tokens_total", "Total LLM tokens used", ["provider"])
    llm_cost_usd_total = Counter("llm_cost_usd_total", "Total LLM cost in USD", ["provider"])
    active_emergencies = Gauge("active_emergencies", "Current open emergency reports")
    risk_alerts_total = Counter("risk_alerts_total", "Total risk alerts generated", ["level"])
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


def record_agent_run(agent_name: str, success: bool, latency_ms: int,
                     tokens: int = 0, cost_usd: float = 0.0, provider: str = "unknown"):
    if PROMETHEUS_AVAILABLE:
        try:
            agent_runs_total.labels(agent_name=agent_name, success=str(success)).inc()
            agent_latency_ms.labels(agent_name=agent_name).observe(latency_ms)
            if tokens:
                llm_tokens_total.labels(provider=provider).inc(tokens)
            if cost_usd:
                llm_cost_usd_total.labels(provider=provider).inc(cost_usd)
        except Exception:
            pass


# ── LangFuse Tracing ─────────────────────────────────────────────────────────
_langfuse = None


def get_langfuse():
    global _langfuse
    if _langfuse is None and settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
        try:
            from langfuse import Langfuse
            _langfuse = Langfuse(
                public_key=settings.LANGFUSE_PUBLIC_KEY,
                secret_key=settings.LANGFUSE_SECRET_KEY,
                host=settings.LANGFUSE_HOST,
            )
        except Exception as e:
            logger.warning(f"LangFuse init failed: {e}")
    return _langfuse


class TraceContext:
    """Context manager for tracing an agent run with LangFuse."""

    def __init__(self, agent_name: str, input_data: dict):
        self.agent_name = agent_name
        self.input_data = input_data
        self.trace = None
        self.span = None
        self.start_time = None
        self.run_id = str(uuid.uuid4())

    def __enter__(self):
        self.start_time = time.time()
        lf = get_langfuse()
        if lf:
            try:
                self.trace = lf.trace(name=self.agent_name, input=self.input_data, id=self.run_id)
            except Exception:
                pass
        return self

    def finish(self, output_data: dict, tokens: int = 0, cost: float = 0.0,
               success: bool = True, provider: str = "unknown"):
        latency = int((time.time() - self.start_time) * 1000)
        if self.trace:
            try:
                self.trace.update(output=output_data, metadata={
                    "tokens": tokens, "cost_usd": cost, "provider": provider
                })
            except Exception:
                pass
        record_agent_run(self.agent_name, success, latency, tokens, cost, provider)
        return latency

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            if self.trace:
                try:
                    self.trace.update(metadata={"error": str(exc_val)})
                except Exception:
                    pass
        return False
