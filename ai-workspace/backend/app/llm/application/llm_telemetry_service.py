import logging
import time
from dataclasses import dataclass

from app.llm.application.llm_gateway import LLMCompletion

logger = logging.getLogger("ai_workspace.llm_telemetry")


@dataclass
class LLMCallRecord:
    execution_id: str
    provider: str | None
    latency_ms: float


class LLMTelemetryService:
    """V1: logs structured records. Token counts and cost are left out on purpose — the
    existing DefaultLLMClient's response shape isn't confirmed to carry usage data (see
    app/integrations/existing_model_client/README.md), so faking those numbers would be worse
    than not reporting them. Add once the real response shape is confirmed."""

    def record_completion(self, execution_id: str, completion: LLMCompletion) -> None:
        record = LLMCallRecord(execution_id=execution_id, provider=completion.provider, latency_ms=0.0)
        logger.info("llm_completion", extra={"record": record})

    def timer(self):
        return _Timer()


class _Timer:
    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc_info):
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000
