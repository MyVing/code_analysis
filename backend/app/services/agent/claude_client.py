import json
import logging
import uuid
from typing import AsyncGenerator

from app.core.config import settings
from app.db.session import async_session
from app.services.agent.llm_client import LLMClient, StreamEvent
from app.services.agent.model_router import ModelConfig, ModelRouter
from app.services.agent.prompt_manager import PromptManager
from app.services.agent.session_manager import SessionManager
from app.tools.base import get_tool_definitions

logger = logging.getLogger(__name__)

prompt_manager = PromptManager()
session_manager = SessionManager()

# Initialize model router from config
_model_pool = [m.strip() for m in settings.MODEL_POOL.split(",") if m.strip()]
model_router = ModelRouter(
    pool=_model_pool,
    strategy=settings.MODEL_ROUTER_STRATEGY,
    base_url=settings.MAAS_BASE_URL,
)

# Initialize unified LLM client
_api_key = settings.MAAS_API_KEY or settings.ANTHROPIC_API_KEY or settings.ANTHROPIC_AUTH_TOKEN or ""
llm_client = LLMClient(api_key=_api_key)


def _get_or_create_session(project_id: uuid.UUID, session_id: str | None) -> tuple[str, ModelConfig]:
    """Get existing session or create new one with a model from the router."""
    if session_id:
        existing_model = session_manager.get_model(session_id)
        if existing_model:
            return session_id, existing_model
        # Session exists but no model (legacy) — assign one
        model_config = model_router.select_model()
        session_manager._session_model[session_id] = model_config
        return session_id, model_config

    # New session
    model_config = model_router.select_model()
    session_id = session_manager.create_session(project_id, model_config)
    return session_id, model_config


async def run_agent_loop(
    project_id: uuid.UUID,
    user_message: str,
    session_id: str | None = None,
    output_schema: dict | None = None,
) -> AsyncGenerator[dict, None]:
    """Run the Agentic Loop and yield SSE events."""

    session_id, model_config = _get_or_create_session(project_id, session_id)
    logger.info(f"Session {session_id[:8]} using model={model_config.model_id}")

    # Build system prompt
    async with async_session() as db:
        if output_schema:
            system_prompt = await prompt_manager.build_structured_system_prompt(db, project_id, output_schema)
        else:
            system_prompt = await prompt_manager.build_system_prompt(db, project_id)

    # Add user message to session
    session_manager.add_message(session_id, {"role": "user", "content": user_message})

    # Get tool definitions
    tools = get_tool_definitions()

    max_iterations = 25
    yielded_report_start = False
    failed_models: set[str] = set()  # track models that have failed

    for iteration in range(max_iterations):
        session_manager.trim_history(session_id, max_messages=40)
        messages = session_manager.get_messages(session_id)

        yield {"event": "thinking", "data": {}}

        # If current model has failed, switch to another one
        if model_config.model_id in failed_models:
            new_config = model_router.select_model(exclude=failed_models)
            if new_config and new_config.model_id != model_config.model_id:
                logger.info(f"Switching model from {model_config.model_id} to {new_config.model_id}")
                model_config = new_config
                session_manager._session_model[session_id] = model_config

        try:
            text_content = ""
            tool_calls = []
            is_final_response = False

            async for event in llm_client.stream_with_tools(
                model=model_config,
                system_prompt=system_prompt,
                messages=messages,
                tools=tools,
                max_tokens=settings.MAX_TOKENS,
            ):
                if event.type == "text_delta":
                    text_content += event.data["content"]
                    if is_final_response:
                        if not yielded_report_start:
                            yield {"event": "report_start", "data": {}}
                            yielded_report_start = True
                        yield {"event": "text", "data": {"content": event.data["content"]}}

                elif event.type == "tool_use_start":
                    tool_calls.append({
                        "id": event.data["id"],
                        "name": event.data["name"],
                        "input": {},
                        "_raw_input": "",
                    })
                    is_final_response = False

                elif event.type == "tool_use_delta":
                    if tool_calls:
                        partial = event.data.get("partial_json", "")
                        if partial:
                            tool_calls[-1]["_raw_input"] += partial

                elif event.type == "tool_use_end":
                    tc = tool_calls[-1] if tool_calls else None
                    if tc:
                        # OpenAI protocol sends full input_json at end
                        input_json = event.data.get("input_json")
                        if input_json:
                            try:
                                tc["input"] = json.loads(input_json)
                            except json.JSONDecodeError:
                                tc["input"] = {}
                        elif "_raw_input" in tc:
                            try:
                                tc["input"] = json.loads(tc.pop("_raw_input"))
                            except json.JSONDecodeError:
                                tc["input"] = {}

                elif event.type == "message_end":
                    # Determine if this was a final response (text only, no tool calls)
                    if not tool_calls:
                        is_final_response = True

            # Process tool calls
            if tool_calls:
                logger.info(f"Agent iteration {iteration}: {len(tool_calls)} tool calls, text_content length={len(text_content)}")
                assistant_content = []
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

                    # Try to extract structured JSON if output_schema is set
                    structured_data = _extract_json(text_content) if output_schema else None

                    if structured_data and output_schema:
                        yield {"event": "structured_result", "data": {"result": structured_data, "schema": output_schema}}
                    else:
                        if not yielded_report_start:
                            yield {"event": "report_start", "data": {}}
                            chunk_size = 50
                            for i in range(0, len(text_content), chunk_size):
                                yield {"event": "text", "data": {"content": text_content[i:i + chunk_size]}}

                    yield {"event": "done", "data": {"session_id": session_id}}
                    return
                else:
                    session_manager.add_message(session_id, {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "好的，我已收集到所需信息。"}],
                    })
                    session_manager.add_message(session_id, {
                        "role": "user",
                        "content": "请根据以上工具调用收集到的信息，直接输出完整的结构化分析报告。不要叙述分析过程，直接给出报告内容。",
                    })
                    continue

        except Exception as e:
            error_msg = str(e)
            is_retryable = any(keyword in error_msg for keyword in ["503", "502", "429", "timeout", "Timeout", "engine timeout"])
            if is_retryable and len(failed_models) < len(_model_pool) - 1:
                logger.warning(f"Model {model_config.model_id} failed, marking for failover: {error_msg}")
                failed_models.add(model_config.model_id)
                yield {"event": "thinking", "data": {}}
                continue  # retry next iteration with a different model
            logger.exception("Agent loop error")
            yield {"event": "error", "data": {"message": str(e)}}
            return

    # Max iterations reached
    logger.warning(f"Agent reached max_iterations={max_iterations}, forcing final report")
    session_manager.add_message(session_id, {
        "role": "user",
        "content": "你已达到最大工具调用次数限制。请立即根据已收集到的信息输出分析报告，不要再调用任何工具。如果某些信息缺失，在报告中说明即可。",
    })

    try:
        text_content = ""
        async for event in llm_client.stream_with_tools(
            model=model_config,
            system_prompt=system_prompt,
            messages=session_manager.get_messages(session_id),
            tools=tools,
            max_tokens=settings.MAX_TOKENS,
        ):
            if event.type == "text_delta":
                text_content += event.data["content"]
                if not yielded_report_start:
                    yield {"event": "report_start", "data": {}}
                    yielded_report_start = True
                yield {"event": "text", "data": {"content": event.data["content"]}}

        if text_content:
            session_manager.add_message(session_id, {"role": "assistant", "content": text_content})
        yield {"event": "done", "data": {"session_id": session_id}}
    except Exception as e:
        logger.exception("Agent forced report error")
        yield {"event": "error", "data": {"message": str(e)}}


async def _execute_tool(project_id: uuid.UUID, tool_name: str, args: dict) -> dict:
    """Execute a tool function and return the result."""
    from app.tools.base import get_tool_function

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


def _extract_json(text: str) -> dict | None:
    """Try to extract a JSON object from AI response text."""
    text = text.strip()
    # Try direct parse
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass
    # Try extracting from markdown code block
    import re
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group(1).strip())
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass
    # Try finding first { ... } pair
    start = text.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            if depth == 0:
                try:
                    result = json.loads(text[start:i + 1])
                    if isinstance(result, dict):
                        return result
                except json.JSONDecodeError:
                    pass
                break
    return None
