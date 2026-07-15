from __future__ import annotations

import random
import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelConfig:
    model_id: str
    base_url: str


# 所有模型统一使用 OpenAI 协议（/v2 端点）
OPENAI_URL_SUFFIX = "/v2"


class ModelRouter:
    def __init__(self, pool: list[str], strategy: str, base_url: str):
        self._pool = pool
        self._strategy = strategy
        self._base_url = base_url.rstrip("/")
        self._counter = 0
        self._lock = threading.Lock()

    def select_model(self, exclude: set[str] | None = None) -> ModelConfig | None:
        available = [m for m in self._pool if not exclude or m not in exclude]
        if not available:
            # Fallback: if all models are excluded, use the full pool
            available = list(self._pool)

        if self._strategy == "random":
            model_id = random.choice(available)
        else:  # round_robin
            with self._lock:
                idx = self._counter % len(available)
                self._counter += 1
            model_id = available[idx]

        url = self._base_url + OPENAI_URL_SUFFIX
        return ModelConfig(model_id=model_id, base_url=url)
