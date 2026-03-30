"""LangGraph graph construction — A2A Multi-Agent Travel Planner.

Flow:
  START → verifier → [Safe?]
    (No)  → END
    (Yes) → orchestrator → [Has params?]
      (No)  → END (asking clarifying question)
      (Yes) → data_fetcher ↔ execute_tools → process_data → planner → present → END
"""

import logging

from langgraph.graph import END, StateGraph, START
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from .state import AgentState
from .nodes import (
    verifier_node,
    retrieve_schema_node,
    route_from_verifier,
    route_from_orchestrator,
    route_from_data_fetcher,
    route_after_tools,
)
from .agents.orchestrator import orchestrator_node
from .agents.planner import planner_node
from .agents.data_fetcher import data_fetcher_node, process_fetched_data
from .tools import get_tools
from .config import config

logger = logging.getLogger(__name__)


def build_graph() -> StateGraph:
    """Build the multi-agent A2A travel planner graph."""
    tools = get_tools()

    workflow = StateGraph(AgentState)

    # ── Add Nodes ─────────────────────────────────────────
    workflow.add_node("verifier", verifier_node)
    workflow.add_node("orchestrator", orchestrator_node)
    workflow.add_node("retrieve_schema", retrieve_schema_node)
    workflow.add_node("data_fetcher", data_fetcher_node)
    workflow.add_node("execute_tools", ToolNode(
        [t for t in tools if callable(t)]
    ))
    workflow.add_node("process_data", process_fetched_data)
    workflow.add_node("planner", planner_node)
    workflow.add_node("present", _present_node)

    # ── Define Edges ──────────────────────────────────────

    # START → Verifier (security gate)
    workflow.add_edge(START, "verifier")

    # Verifier → Orchestrator or END
    workflow.add_conditional_edges(
        "verifier",
        route_from_verifier,
        {"__end__": END, "orchestrator": "orchestrator"},
    )

    # Orchestrator → Data Fetcher (if params) or END (clarifying question)
    workflow.add_conditional_edges(
        "orchestrator",
        route_from_orchestrator,
        {"data_fetcher": "retrieve_schema", "__end__": END},
    )

    # Schema retrieval → Data Fetcher
    workflow.add_edge("retrieve_schema", "data_fetcher")

    # Data Fetcher → execute_tools or process_data
    workflow.add_conditional_edges(
        "data_fetcher",
        route_from_data_fetcher,
        {
            "execute_tools": "execute_tools",
            "process_data": "process_data",
        },
    )

    # Tool execution → back to Data Fetcher
    workflow.add_edge("execute_tools", "data_fetcher")

    # Process data → Planner
    workflow.add_edge("process_data", "planner")

    # Planner → Present
    workflow.add_edge("planner", "present")

    # Present → END
    workflow.add_edge("present", END)

    # ── Compile ───────────────────────────────────────────
    memory = MemorySaver()
    graph = workflow.compile(checkpointer=memory)

    logger.info("A2A Travel Planner graph compiled with %d tools.", len(tools))

    return graph


def _present_node(state: dict) -> dict:
    """Final presentation node — orchestrator formats the itinerary."""
    return orchestrator_node(state)


def create_agent():
    """Create the travel planner agent graph with run config."""
    graph = build_graph()

    run_config = {
        "configurable": {"thread_id": "default"},
        "recursion_limit": config.max_recursion_limit,
    }

    return graph, run_config
