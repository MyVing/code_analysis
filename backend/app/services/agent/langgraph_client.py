from __future__ import annotations

import json
import logging
import uuid
from typing import AsyncGenerator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode

from app.core.config import settings
from app.db.session import async_session
from app.services.agent.langchain_tools import create_langchain_tools
from app.services.agent.model_pool import ModelPool, ModelPoolExhaustedError, ModelPoolTimeoutError
from app.services.agent.prompt_manager import PromptManager

logger = logging.getLogger(__name__)

prompt_manager = PromptManager()

model_pool = ModelPool.from_config(
    pool_json=settings.MODEL_POOL_CONFIG,
    default_base_url=settings.MODEL_DEFAULT_BASE_URL or settings.LLM_BASE_URL,
    default_api_key=settings.MODEL_DEFAULT_API_KEY or settings.LLM_API_KEY or "",
    strategy=settings.MODEL_ROUTER_STRATEGY,
    max_queue_size=settings.MODEL_POOL_MAX_QUEUE_SIZE,
    acquire_timeout=settings.MODEL_POOL_ACQUIRE_TIMEOUT,
)


class AgentState(MessagesState):
    pass


def _should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return END


async def run_agent_loop(
    project_id: uuid.UUID,
    user_message: str,
    session_id: str | None = None,
    output_schema: dict | None = None,
) -> AsyncGenerator[dict, None]:
    """Run the ReAct agent loop via LangGraph and yield SSE events."""

    try:
        slot = await model_pool.acquire()
    except ModelPoolExhaustedError:
        yield {"event": "error", "data": {"message": "系统繁忙，请稍后重试"}}
        return
    except ModelPoolTimeoutError:
        yield {"event": "error", "data": {"message": "等待超时，所有模型忙碌，请稍后重试"}}
        return

    logger.info(f"Session using model={slot.model_id} from pool (concurrency={slot._concurrency}/{slot.max_concurrency})")

    try:
        # 1. Build system prompt
        async with async_session() as db:
            if output_schema:
                system_prompt = await prompt_manager.build_structured_system_prompt(db, project_id, output_schema)
            else:
                system_prompt = await prompt_manager.build_system_prompt(db, project_id)

        # 2. Create LangChain tools with db + project_id injection
        async with async_session() as db:
            tools = create_langchain_tools(db, project_id)

        # 3. Get LLM instance with tools bound
        llm = slot.get_llm(
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
        ).bind_tools(tools)

        # 4. Build agent node
        async def agent_node(state: AgentState):
            response = await llm.ainvoke(state["messages"])
            return {"messages": [response]}

        # 5. Build graph
        tool_node = ToolNode(tools)
        graph = StateGraph(AgentState)
        graph.add_node("agent", agent_node)
        graph.add_node("tools", tool_node)
        graph.add_edge(START, "agent")
        graph.add_conditional_edges("agent", _should_continue, {"tools": "tools", END: END})
        graph.add_edge("tools", "agent")
        app = graph.compile()

        # 6. Prepare initial messages
        messages: list = [SystemMessage(content=system_prompt), HumanMessage(content=user_message)]

        # 7. Stream events and convert to SSE
        yielded_report_start = False
        current_tool_calls: dict[str, dict] = {}  # id -> {name, args}

        async for event in app.astream_events(
            {"messages": messages},
            version="v2",
        ):
            kind = event["event"]
            data = event.get("data", {})

            if kind == "on_chat_model_start":
                yield {"event": "thinking", "data": {}}

            elif kind == "on_chat_model_stream":
                chunk = data.get("chunk")
                if chunk is None:
                    continue

                # Tool call chunks
                if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
                    for tc_chunk in chunk.tool_call_chunks:
                        tc_id = tc_chunk.get("id") or tc_chunk.get("name", "unknown")
                        if tc_id not in current_tool_calls:
                            current_tool_calls[tc_id] = {
                                "id": tc_chunk.get("id", ""),
                                "name": tc_chunk.get("name", ""),
                                "args": "",
                            }
                        if tc_chunk.get("args"):
                            current_tool_calls[tc_id]["args"] += tc_chunk["args"]
                    continue

                # Text content chunks
                if hasattr(chunk, "content") and chunk.content:
                    if not yielded_report_start:
                        yield {"event": "report_start", "data": {}}
                        yielded_report_start = True
                    yield {"event": "text", "data": {"content": chunk.content}}

            elif kind == "on_tool_start":
                tool_name = data.get("name", "unknown")
                tool_input = data.get("input", {})
                yield {"event": "tool_call", "data": {"tool": tool_name, "args": tool_input}}

            elif kind == "on_tool_end":
                output = data.get("output", "")
                content = output.content if hasattr(output, "content") else str(output)
                yield {"event": "tool_result", "data": {"tool": "unknown", "result": content}}

        # 8. Emit done
        yield {"event": "done", "data": {"session_id": session_id or ""}}

    except Exception as e:
        logger.exception("Agent loop error")
        yield {"event": "error", "data": {"message": str(e)}}
    finally:
        await model_pool.release(slot.model_id)
