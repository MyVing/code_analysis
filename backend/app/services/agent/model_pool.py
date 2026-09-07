from __future__ import annotations

import asyncio
import json
import logging
import random
from dataclasses import dataclass, field

from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


class ModelPoolExhaustedError(Exception):
    """队列已满，无法接纳更多等待请求。"""


class ModelPoolTimeoutError(Exception):
    """等待超时，所有模型忙碌。"""


@dataclass
class ModelSlot:
    model_id: str
    base_url: str
    api_key: str
    max_concurrency: int = 5
    _concurrency: int = field(default=0, repr=False)
    _llm_instance: ChatOpenAI | None = field(default=None, repr=False)

    @property
    def available(self) -> int:
        return max(0, self.max_concurrency - self._concurrency)

    def get_llm(self, temperature: float = 0.7, max_tokens: int = 4096) -> ChatOpenAI:
        if self._llm_instance is None:
            self._llm_instance = ChatOpenAI(
                model=self.model_id,
                base_url=self.base_url,
                api_key=self.api_key,
                temperature=temperature,
                max_tokens=max_tokens,
                streaming=True,
            )
        return self._llm_instance


class ModelPool:
    """并发感知模型池：优先选择最空闲的模型，满时排队等待。"""

    def __init__(
        self,
        slots: list[ModelSlot],
        strategy: str = "least_busy",
        max_queue_size: int = 20,
        acquire_timeout: int = 30,
    ):
        self._slots: dict[str, ModelSlot] = {s.model_id: s for s in slots}
        self._strategy = strategy
        self._lock = asyncio.Lock()
        self._counter = 0
        self._wait_queue: asyncio.Queue[asyncio.Future] = asyncio.Queue(maxsize=max_queue_size)
        self._acquire_timeout = acquire_timeout

    @classmethod
    def from_config(
        cls,
        pool_json: str,
        default_base_url: str,
        default_api_key: str,
        strategy: str,
        max_queue_size: int = 20,
        acquire_timeout: int = 30,
    ) -> ModelPool:
        """从 JSON 配置字符串构建模型池。"""
        try:
            configs = json.loads(pool_json)
        except json.JSONDecodeError:
            logger.error("MODEL_POOL_CONFIG JSON parse failed, falling back to empty pool")
            configs = []

        slots: list[ModelSlot] = []
        for cfg in configs:
            model_id = cfg.get("model_id", "").strip()
            if not model_id:
                continue
            slots.append(ModelSlot(
                model_id=model_id,
                base_url=cfg.get("base_url") or default_base_url,
                api_key=cfg.get("api_key") or default_api_key,
                max_concurrency=cfg.get("max_concurrency", 5),
            ))

        if not slots:
            logger.warning("Model pool is empty — no models configured")

        return cls(slots, strategy, max_queue_size, acquire_timeout)

    @property
    def model_ids(self) -> list[str]:
        return list(self._slots.keys())

    def _pick(self, candidates: list[ModelSlot]) -> ModelSlot:
        if self._strategy == "least_busy":
            return min(candidates, key=lambda s: s._concurrency)
        elif self._strategy == "random":
            return random.choice(candidates)
        else:  # round_robin
            slot = candidates[self._counter % len(candidates)]
            self._counter += 1
            return slot

    async def acquire(self, exclude: set[str] | None = None, timeout: float | None = None) -> ModelSlot:
        """获取最空闲的模型，并发计数 +1。满时排队等待，超时或队列满则抛异常。"""
        timeout = timeout if timeout is not None else self._acquire_timeout

        async with self._lock:
            candidates = [s for s in self._slots.values()
                          if (not exclude or s.model_id not in exclude)
                          and s._concurrency < s.max_concurrency]
            if candidates:
                slot = self._pick(candidates)
                slot._concurrency += 1
                logger.info(f"Acquired model={slot.model_id}, concurrency={slot._concurrency}/{slot.max_concurrency}")
                return slot

        # 无可用槽位，入队等待
        if self._wait_queue.full():
            logger.warning("Wait queue is full, rejecting request")
            raise ModelPoolExhaustedError("Queue is full, please retry later")

        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        self._wait_queue.put_nowait(future)

        logger.info(f"Queued for model slot, queue_size={self._wait_queue.qsize()}, timeout={timeout}s")
        try:
            slot = await asyncio.wait_for(future, timeout=timeout)
            logger.info(f"Acquired model={slot.model_id} from queue, concurrency={slot._concurrency}/{slot.max_concurrency}")
            return slot
        except asyncio.TimeoutError:
            if not future.done():
                future.cancel()
            logger.warning(f"Acquire timed out after {timeout}s")
            raise ModelPoolTimeoutError("Wait timed out, all models busy")

    async def release(self, model_id: str) -> None:
        """释放模型，并发计数 -1，并唤醒队列中的下一个等待者。"""
        async with self._lock:
            slot = self._slots.get(model_id)
            if slot and slot._concurrency > 0:
                slot._concurrency -= 1
                logger.info(f"Released model={model_id}, concurrency={slot._concurrency}/{slot.max_concurrency}")

                # 优先唤醒队列中的等待者
                while not self._wait_queue.empty():
                    future = self._wait_queue.get_nowait()
                    if future.done():
                        continue  # 已超时取消，跳过
                    candidates = [s for s in self._slots.values() if s._concurrency < s.max_concurrency]
                    if candidates:
                        picked = self._pick(candidates)
                        picked._concurrency += 1
                        future.set_result(picked)
                        break
                    else:
                        # 没有可用槽位了，放回队列头部
                        self._wait_queue.put_nowait(future)
                        break

    def get_fallback_model(self, exclude_model_id: str | None = None) -> ModelSlot | None:
        """获取一个不同的模型作为 fallback。"""
        candidates = [s for s in self._slots.values()
                      if s.model_id != exclude_model_id]
        if not candidates:
            return None
        return min(candidates, key=lambda s: s._concurrency)
