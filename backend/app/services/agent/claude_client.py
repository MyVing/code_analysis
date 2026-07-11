import json
import logging
import uuid
from typing import AsyncGenerator

import anthropic

from app.core.config import settings
from app.db.session import async_session
from app.services.agent.prompt_manager import PromptManager
from app.services.agent.session_manager import SessionManager
from app.tools.base import get_tool_definitions, get_tool_function

logger = logging.getLogger(__name__)

prompt_manager = PromptManager()
session_manager = SessionManager()


def _create_client() -> anthropic.AsyncAnthropic:
    if settings.ANTHROPIC_AUTH_TOKEN:
        return anthropic.AsyncAnthropic(
            auth_token=settings.ANTHROPIC_AUTH_TOKEN,
            base_url=settings.ANTHROPIC_BASE_URL,
        )
    if settings.ANTHROPIC_API_KEY:
        return anthropic.AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            base_url=settings.ANTHROPIC_BASE_URL,
        )
    raise ValueError("ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN must be set")


async def run_agent_loop(
    project_id: uuid.UUID,
    user_message: str,
    session_id: str | None = None,
) -> AsyncGenerator[dict, None]:
    """Run the Agentic Loop and yield SSE events."""

    if not session_id:
        session_id = session_manager.create_session(project_id)

    # Build system prompt
    async with async_session() as db:
        system_prompt = await prompt_manager.build_system_prompt(db, project_id)

    # Add user message to session
    session_manager.add_message(session_id, {"role": "user", "content": user_message})

    # Get tool definitions
    tools = get_tool_definitions()

    client = _create_client()

    max_iterations = 10
    for _ in range(max_iterations):
        session_manager.trim_history(session_id, max_messages=40)
        messages = session_manager.get_messages(session_id)

        yield {"event": "thinking", "data": {}}

        try:
            text_content = ""
            tool_calls = []

            async with client.messages.stream(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=settings.MAX_TOKENS,
                system=system_prompt,
                messages=messages,
                tools=tools,
            ) as stream:
                async for event in stream:
                    if event.type == "content_block_start":
                        if event.content_block.type == "tool_use":
                            tool_calls.append({
                                "id": event.content_block.id,
                                "name": event.content_block.name,
                                "input": {},
                            })
                    elif event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            text_content += event.delta.text
                            yield {"event": "text", "data": {"content": event.delta.text}}
                        elif event.delta.type == "input_json_delta":
                            if tool_calls:
                                partial = getattr(event.delta, "partial_json", "")
                                if partial:
                                    tool_calls[-1].setdefault("_raw_input", "")
                                    tool_calls[-1]["_raw_input"] += partial
                    elif event.type == "content_block_stop":
                        if tool_calls and "_raw_input" in tool_calls[-1]:
                            try:
                                tool_calls[-1]["input"] = json.loads(tool_calls[-1].pop("_raw_input"))
                            except json.JSONDecodeError:
                                tool_calls[-1]["input"] = {}

            # Process tool calls
            if tool_calls:
                assistant_content = []
                if text_content:
                    assistant_content.append({"type": "text", "text": text_content})
                for tc in tool_calls:
                    assistant_content.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["name"],
                        "input": tc["input"],
                    })
                    yield {
                        "event": "tool_call",
                        "data": {"tool": tc["name"], "args": tc["input"]},
                    }

                session_manager.add_message(session_id, {"role": "assistant", "content": assistant_content})

                tool_results = []
                for tc in tool_calls:
                    result = await _execute_tool(project_id, tc["name"], tc["input"])
                    yield {"event": "tool_result", "data": {"tool": tc["name"], "result": result}}
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tc["id"],
                        "content": json.dumps(result, ensure_ascii=False),
                    })

                session_manager.add_message(session_id, {"role": "user", "content": tool_results})
                continue
            else:
                if text_content:
                    session_manager.add_message(session_id, {"role": "assistant", "content": text_content})
                yield {"event": "done", "data": {"session_id": session_id}}
                return

        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}")
            yield {"event": "error", "data": {"message": f"AI service error: {e.message}"}}
            return
        except Exception as e:
            logger.exception("Agent loop error")
            yield {"event": "error", "data": {"message": str(e)}}
            return

    yield {"event": "done", "data": {"session_id": session_id, "reason": "max_iterations"}}


async def _execute_tool(project_id: uuid.UUID, tool_name: str, args: dict) -> dict:
    """Execute a tool function and return the result."""
    func = get_tool_function(tool_name)
    if not func:
        return {"error": f"Unknown tool: {tool_name}"}

    try:
        async with async_session() as db:
            result = await func(db, project_id, **args)
            return result
    except Exception as e:
        logger.exception(f"Tool execution error: {tool_name}")
        return {"error": str(e)}
