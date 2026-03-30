"""LangGraph node functions for the A2A Travel Planner workflow.

Wraps the agent logic from agent/agents/ and provides routing functions.
"""

import logging
from typing import Dict

from langchain_core.messages import AIMessage, HumanMessage

from .config import config
from .agents.orchestrator import orchestrator_node
from .agents.planner import planner_node
from .agents.data_fetcher import data_fetcher_node, process_fetched_data
from .tools import get_schema_from_bq
from .guardrails import check_prompt_injection
from .prompts import VERIFIER_PROMPT

from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)


# ── Node: Security Verifier ──────────────────────────────

def verifier_node(state: Dict) -> Dict:
    """CaMeL-style dual-layer security gatekeeper.

    Stage 1: Static regex pre-screen (code-level, deterministic)
    Stage 2: LLM semantic intent analysis
    """
    logger.info("Verifier Agent analyzing prompt...")

    last_user_msg = None
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_user_msg = msg.content
            break

    if not last_user_msg:
        return {
            "messages": [AIMessage(content="REJECT: No user input detected.", name="Verifier")],
            "sender": "Verifier",
        }

    # Stage 1: Static CaMeL Pre-Screen
    static_check = check_prompt_injection(last_user_msg)
    if not static_check.is_valid:
        logger.warning("CaMeL static filter blocked: %s", static_check.rejection_reason)
        return {
            "messages": [AIMessage(content=static_check.rejection_reason, name="Verifier")],
            "sender": "Verifier",
        }

    # Stage 2: LLM Verifier
    llm = ChatGoogleGenerativeAI(
        model=config.gemini_model,
        api_key=config.google_api_key,
        temperature=0,
    )
    response = llm.invoke([
        SystemMessage(content=VERIFIER_PROMPT),
        HumanMessage(content=last_user_msg),
    ])
    response.name = "Verifier"

    return {"messages": [response], "sender": "Verifier"}


# ── Node: Retrieve Schema ────────────────────────────────

def retrieve_schema_node(state: Dict) -> Dict:
    """Fetch and cache the BigQuery dataset schema."""
    if state.get("dataset_schema") is None:
        logger.info("Fetching schema from BigQuery...")
        try:
            schema = get_schema_from_bq()
            return {
                "dataset_schema": schema,
                "messages": [AIMessage(content="Schema retrieved from BigQuery.", name="System")],
                "sender": "System",
            }
        except Exception as e:
            logger.warning("Could not fetch BQ schema: %s (continuing without it)", e)
            return {
                "dataset_schema": "{}",
                "sender": "System",
            }
    return {"sender": "System"}


# ── Routing Functions ────────────────────────────────────

def route_from_verifier(state: Dict) -> str:
    """Verifier → REJECT (end) or → Orchestrator (continue)."""
    last_message = state["messages"][-1]
    content = getattr(last_message, "content", "")

    if content.startswith("REJECT:") or content.startswith("BLOCKED"):
        return "__end__"
    return "orchestrator"


def route_from_orchestrator(state: Dict) -> str:
    """Orchestrator → Data Fetcher (if travel params extracted) or → END."""
    travel_params = state.get("travel_params")
    if travel_params and travel_params.get("destination"):
        return "data_fetcher"
    # No valid params = orchestrator is asking clarifying question → end turn
    return "__end__"


def route_from_data_fetcher(state: Dict) -> str:
    """Data Fetcher → execute_tools (if tool calls) or → process data."""
    last_message = state["messages"][-1]

    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        tool_names = [tc["name"] for tc in last_message.tool_calls]

        # If the agent submitted final fetched data, process it
        if "SubmitFetchedData" in tool_names:
            return "process_data"
        if "SubmitFinalAnswer" in tool_names:
            return "process_data"

        return "execute_tools"

    # No tool calls = LLM responded with text, process what we have
    return "process_data"


def route_after_tools(state: Dict) -> str:
    """After tool execution → back to data_fetcher for more calls or processing."""
    return "data_fetcher"
