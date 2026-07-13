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
    yielded_report_start = False
    for iteration in range(max_iterations):
        session_manager.trim_history(session_id, max_messages=40)
        messages = session_manager.get_messages(session_id)

        yield {"event": "thinking", "data": {}}

        try:
            text_content = ""
            tool_calls = []
            is_final_response = False

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
                        elif event.content_block.type == "text":
                            # First text block with no prior tool_use = final response
                            if not tool_calls:
                                is_final_response = True
                    elif event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            text_content += event.delta.text
                            # Stream text in real-time during the final response
                            if is_final_response:
                                if not yielded_report_start:
                                    yield {"event": "report_start", "data": {}}
                                    yielded_report_start = True
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
                        # If a tool_use block appears after text, this wasn't the final response
                        if tool_calls:
                            is_final_response = False

            # Process tool calls
            if tool_calls:
                logger.info(f"Agent iteration {iteration}: {len(tool_calls)} tool calls, text_content length={len(text_content)}")
                assistant_content = []
                # Do NOT include intermediate text in session history —
                # this prevents AI from thinking it already answered,
                # and forces it to output a complete report in the final iteration
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
                # Final response
                logger.info(f"Agent final response: text_content length={len(text_content)}, preview={text_content[:200]!r}")
                if text_content:
                    session_manager.add_message(session_id, {"role": "assistant", "content": text_content})
                    if not yielded_report_start:
                        # Text was accumulated but not streamed (edge case), send now in chunks
                        yield {"event": "report_start", "data": {}}
                        chunk_size = 50
                        for i in range(0, len(text_content), chunk_size):
                            yield {"event": "text", "data": {"content": text_content[i:i + chunk_size]}}
                    yield {"event": "done", "data": {"session_id": session_id}}
                    return
                else:
                    # AI returned empty text with no tool calls — give it another chance
                    # with an explicit prompt to generate the report
                    session_manager.add_message(session_id, {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "好的，我已收集到所需信息。"}],
                    })
                    session_manager.add_message(session_id, {
                        "role": "user",
                        "content": "请根据以上工具调用收集到的信息，直接输出完整的结构化分析报告。不要叙述分析过程，直接给出报告内容。",
                    })
                    continue

        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}")
            yield {"event": "error", "data": {"message": f"AI service error: {e.message}"}}
            return
        except Exception as e:
            logger.exception("Agent loop error")
            yield {"event": "error", "data": {"message": str(e)}}
            return

    # Max iterations reached — force AI to output a report with what it has
    logger.warning(f"Agent reached max_iterations={max_iterations}, forcing final report")
    session_manager.add_message(session_id, {
        "role": "user",
        "content": "你已达到最大工具调用次数限制。请立即根据已收集到的信息输出分析报告，不要再调用任何工具。如果某些信息缺失，在报告中说明即可。",
    })

    try:
        text_content = ""
        async with client.messages.stream(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=settings.MAX_TOKENS,
            system=system_prompt,
            messages=session_manager.get_messages(session_id),
        ) as stream:
            async for event in stream:
                if event.type == "content_block_delta" and event.delta.type == "text_delta":
                    text_content += event.delta.text
                    if not yielded_report_start:
                        yield {"event": "report_start", "data": {}}
                        yielded_report_start = True
                    yield {"event": "text", "data": {"content": event.delta.text}}

        if text_content:
            session_manager.add_message(session_id, {"role": "assistant", "content": text_content})
        yield {"event": "done", "data": {"session_id": session_id}}
    except Exception as e:
        logger.exception("Agent forced report error")
        yield {"event": "error", "data": {"message": str(e)}}


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
