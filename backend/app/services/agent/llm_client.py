from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import AsyncGenerator

import httpx

from app.services.agent.model_router import ModelConfig

logger = logging.getLogger(__name__)

# HTTP status codes that are retryable
_RETRYABLE_STATUS = {429, 502, 503, 504}


@dataclass
class StreamEvent:
    type: str  # text_delta | tool_use_start | tool_use_delta | tool_use_end | message_end
    data: dict


def _anthropic_messages_to_openai(messages: list[dict]) -> list[dict]:
    """Convert Anthropic-format messages to OpenAI format."""
    result: list[dict] = []
    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        if role == "user" and isinstance(content, list):
            tool_results = []
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    tool_results.append(block)
                elif isinstance(block, str):
                    text_parts.append(block)
                elif isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))

            for tr in tool_results:
                content_str = tr.get("content", "")
                if isinstance(content_str, list):
                    content_str = " ".join(
                        b.get("text", str(b)) if isinstance(b, dict) else str(b) for b in content_str
                    )
                result.append({
                    "role": "tool",
                    "tool_call_id": tr["tool_use_id"],
                    "content": content_str,
                })
            if text_parts:
                result.append({"role": "user", "content": "\n".join(text_parts)})

        elif role == "assistant" and isinstance(content, list):
            tool_calls = []
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool_calls.append({
                        "id": block["id"],
                        "type": "function",
                        "function": {
                            "name": block["name"],
                            "arguments": json.dumps(block.get("input", {}), ensure_ascii=False),
                        },
                    })
                elif isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))

            assistant_msg: dict = {"role": "assistant"}
            if text_parts:
                assistant_msg["content"] = "\n".join(text_parts)
            else:
                assistant_msg["content"] = None
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            result.append(assistant_msg)

        elif isinstance(content, str):
            result.append({"role": role, "content": content})
        else:
            result.append({"role": role, "content": str(content)})

    return result


class LLMClient:
    """LLM client using OpenAI protocol via httpx."""

    def __init__(self, api_key: str, max_retries: int = 3):
        self._api_key = api_key
        self._max_retries = max_retries
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=15, read=600, write=30, pool=15),
        )

    async def stream_with_tools(
        self,
        model: ModelConfig,
        system_prompt: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int,
    ) -> AsyncGenerator[StreamEvent, None]:
        openai_messages = _anthropic_messages_to_openai(messages)
        openai_messages.insert(0, {"role": "system", "content": system_prompt})

        payload: dict = {
            "model": model.model_id,
            "messages": openai_messages,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            current_tool_calls: dict[int, dict] = {}
            try:
                async with self._client.stream(
                    "POST",
                    model.base_url + "/chat/completions",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                ) as response:
                    if response.status_code in _RETRYABLE_STATUS:
                        body = await response.aread()
                        error_msg = f"LLM API error {response.status_code}: {body.decode('utf-8', errors='replace')[:500]}"
                        logger.warning(f"Retryable error (attempt {attempt + 1}/{self._max_retries}): {error_msg}")
                        last_error = Exception(error_msg)
                        delay = 2 ** attempt + 1  # 2s, 3s, 5s
                        await asyncio.sleep(delay)
                        continue

                    if response.status_code != 200:
                        body = await response.aread()
                        raise Exception(f"LLM API error {response.status_code}: {body.decode('utf-8', errors='replace')[:500]}")

                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data = line[6:]
                        if data.strip() == "[DONE]":
                            if current_tool_calls:
                                for idx, tc in current_tool_calls.items():
                                    yield StreamEvent("tool_use_end", {
                                        "id": tc["id"],
                                        "name": tc["name"],
                                        "input_json": tc["arguments_str"],
                                    })
                                current_tool_calls.clear()
                            yield StreamEvent("message_end", {})
                            return

                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue

                        choices = chunk.get("choices", [])
                        if not choices:
                            continue

                        delta = choices[0].get("delta", {})

                        # Text content
                        content = delta.get("content")
                        if content:
                            yield StreamEvent("text_delta", {"content": content})

                        # Tool calls
                        tc_list = delta.get("tool_calls")
                        if tc_list:
                            for tc_delta in tc_list:
                                idx = tc_delta.get("index", 0)
                                if idx not in current_tool_calls:
                                    current_tool_calls[idx] = {
                                        "id": tc_delta.get("id", ""),
                                        "name": "",
                                        "arguments_str": "",
                                    }
                                    if tc_delta.get("id"):
                                        current_tool_calls[idx]["id"] = tc_delta["id"]

                                    func = tc_delta.get("function", {})
                                    if func.get("name"):
                                        current_tool_calls[idx]["name"] = func["name"]

                                    yield StreamEvent("tool_use_start", {
                                        "id": current_tool_calls[idx]["id"],
                                        "name": current_tool_calls[idx]["name"],
                                    })
                                else:
                                    func = tc_delta.get("function", {})
                                    if func.get("name"):
                                        current_tool_calls[idx]["name"] = func["name"]

                                func = tc_delta.get("function", {})
                                if func.get("arguments"):
                                    current_tool_calls[idx]["arguments_str"] += func["arguments"]
                                    yield StreamEvent("tool_use_delta", {
                                        "partial_json": func["arguments"],
                                    })

                        # Finish reason
                        finish_reason = choices[0].get("finish_reason")
                        if finish_reason:
                            for idx, tc in current_tool_calls.items():
                                yield StreamEvent("tool_use_end", {
                                    "id": tc["id"],
                                    "name": tc["name"],
                                    "input_json": tc["arguments_str"],
                                })
                            current_tool_calls.clear()
                            yield StreamEvent("message_end", {})

                    # Stream ended normally
                    return

            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.PoolTimeout) as e:
                logger.warning(f"Timeout error (attempt {attempt + 1}/{self._max_retries}): {e}")
                last_error = e
                delay = 2 ** attempt + 1
                await asyncio.sleep(delay)
                continue
            except httpx.HTTPStatusError as e:
                if e.response.status_code in _RETRYABLE_STATUS:
                    logger.warning(f"Retryable HTTP error (attempt {attempt + 1}/{self._max_retries}): {e}")
                    last_error = e
                    delay = 2 ** attempt + 1
                    await asyncio.sleep(delay)
                    continue
                raise

        # All retries exhausted
        raise last_error or Exception("LLM request failed after all retries")
